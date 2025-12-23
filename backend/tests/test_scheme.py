import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# 导入应用和依赖
from app.main import app
from app.core.database import get_session
from app.models.dataset import DatasetMeta, DatasetConfig
from app.models.llm_model import LLMModel
from app.models.scheme import EvaluationScheme
from app.models.task import EvaluationTask

# ==========================================
# 1. 搭建临时测试环境 (In-Memory SQLite)
# ==========================================

# 使用内存数据库，确保测试不污染真实数据
engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)

def get_test_session():
    with Session(engine) as session:
        yield session

# 覆盖 FastAPI 的依赖注入
app.dependency_overrides[get_session] = get_test_session

client = TestClient(app)

# 初始化数据库表结构
@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

# ==========================================
# 2. 准备基础数据 (Fixtures)
# ==========================================

@pytest.fixture(name="setup_data")
def setup_data_fixture(session: Session):
    # A. 创建一个模型
    model = LLMModel(name="Test-Model-7B", path="/tmp/model", type="hf")
    session.add(model)
    
    # B. 创建两个数据集配置
    meta = DatasetMeta(name="MMLU", category="Knowledge")
    session.add(meta)
    session.commit()
    
    config1 = DatasetConfig(
        meta_id=meta.id, 
        config_name="MMLU_Gen", 
        mode="gen", 
        file_path="/tmp/mmlu.jsonl",
        display_metric="Accuracy"
    )
    config2 = DatasetConfig(
        meta_id=meta.id, 
        config_name="MMLU_PPL", 
        mode="ppl", 
        file_path="/tmp/mmlu_ppl.jsonl",
        display_metric="Perplexity"
    )
    session.add(config1)
    session.add(config2)
    session.commit()
    
    return {
        "model_id": model.id,
        "config_ids": [config1.id, config2.id]
    }

# ==========================================
# 3. 测试用例
# ==========================================

def test_create_and_read_scheme(session: Session, setup_data):
    """测试创建和读取评测方案"""
    config_ids = setup_data["config_ids"]
    
    # --- 1. 创建方案 ---
    payload = {
        "name": "Standard Benchmark v1",
        "description": "Knowledge heavy benchmark",
        "dataset_config_ids": config_ids
    }
    response = client.post("/api/v1/schemes/", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    # 验证返回的 ID 列表是否正确
    assert set(data["dataset_config_ids"]) == set(config_ids)
    scheme_id = data["id"]

    # --- 2. 读取方案列表 ---
    response = client.get("/api/v1/schemes/")
    assert response.status_code == 200
    list_data = response.json()
    
    # 验证列表中包含刚才创建的方案
    found = next((s for s in list_data if s["id"] == scheme_id), None)
    assert found is not None
    assert found["dataset_config_ids"] == config_ids
    
    # --- 3. 验证数据库关联 (Many-to-Many) ---
    # 直接查询数据库验证 Link 表是否写入
    scheme = session.get(EvaluationScheme, scheme_id)
    assert len(scheme.configs) == 2


def test_create_task_from_scheme(session: Session, setup_data):
    """测试通过 scheme_id 创建评测任务"""
    model_id = setup_data["model_id"]
    config_ids = setup_data["config_ids"]

    # 1. 先创建一个方案
    scheme_payload = {
        "name": "Quick Test Scheme",
        "dataset_config_ids": config_ids
    }
    scheme_res = client.post("/api/v1/schemes/", json=scheme_payload)
    scheme_id = scheme_res.json()["id"]

    # 2. 通过 scheme_id 创建任务
    task_payload = {
        "model_id": model_id,
        "scheme_id": scheme_id,
        # 注意：这里我们故意不传 config_ids，测试是否自动填充
        "config_ids": [] 
    }
    
    response = client.post("/api/v1/tasks/", json=task_payload)
    
    assert response.status_code == 200
    task_data = response.json()
    
    # 验证
    assert task_data["scheme_id"] == scheme_id
    assert task_data["model_id"] == model_id
    
    # 检查任务是否正确关联了方案中的数据集
    # 由于 task_schema.py 的 Response 可能没返回 datasets_list 字段，我们查库验证
    task_db = session.get(EvaluationTask, task_data["id"])
    import json
    saved_ids = json.loads(task_db.datasets_list)
    assert set(saved_ids) == set(config_ids)


def test_scheme_isolation(session: Session, setup_data):
    """测试删除数据集对方案的影响 (验证 Link 表逻辑)"""
    config_id = setup_data["config_ids"][0]
    
    # 1. 创建方案包含 config_id
    scheme_payload = {"name": "Isolation Test", "dataset_config_ids": [config_id]}
    s_res = client.post("/api/v1/schemes/", json=scheme_payload)
    scheme_id = s_res.json()["id"]
    
    # 2. 删除该数据集配置
    # 注意：这需要后端接口支持，或者我们直接操作数据库
    config_to_del = session.get(DatasetConfig, config_id)
    session.delete(config_to_del)
    session.commit()
    
    # 3. 再次查询方案
    # 预期：方案仍然存在，但 configs 列表应该变空了 (因为关联的数据没了)
    scheme = session.get(EvaluationScheme, scheme_id)
    assert len(scheme.configs) == 0
    
    # 4. 尝试通过该方案创建任务 -> 应该报错 (400)
    task_payload = {
        "model_id": setup_data["model_id"],
        "scheme_id": scheme_id
    }
    res = client.post("/api/v1/tasks/", json=task_payload)
    assert res.status_code == 400
    assert "未包含任何有效的数据集" in res.json()["detail"]