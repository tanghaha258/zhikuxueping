from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    subject: str = Field(..., description="学科")
    grade: str = Field(..., description="年级")
    question_type: str = Field(..., description="题型")
    difficulty: int = Field(3, ge=1, le=5, description="难度 1-5")
    content: str = Field(..., description="题目内容(HTML)")
    options: Optional[str] = Field(None, description="选择题选项 JSON")
    answer: Optional[str] = Field(None, description="答案")
    analysis: Optional[str] = Field(None, description="解析(HTML)")
    score: float = Field(5.0, description="默认分值")
    knowledge_points: str = Field("[]", description="知识点 JSON")


class QuestionUpdate(BaseModel):
    subject: Optional[str] = None
    grade: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[int] = None
    content: Optional[str] = None
    options: Optional[str] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: Optional[float] = None
    knowledge_points: Optional[str] = None
    status: Optional[str] = None


class QuestionResponse(BaseModel):
    id: str
    subject: str
    grade: str
    question_type: str
    difficulty: int
    content: str
    options: Optional[str] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: float
    knowledge_points: str
    source: str
    status: str
    usage_count: int
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AiGenerateRequest(BaseModel):
    subject: str = Field(..., description="学科")
    grade: str = Field(..., description="年级")
    question_type: str = Field(..., description="题型")
    knowledge_points: list[str] = Field(default_factory=list, description="知识点列表")
    count: int = Field(5, ge=1, le=20, description="生成数量")
    difficulty: int = Field(3, ge=1, le=5, description="难度")


class BatchImportItem(BaseModel):
    subject: str = Field(..., description="学科")
    grade: str = Field(..., description="年级")
    question_type: str = Field(..., description="题型")
    difficulty: int = Field(3, ge=1, le=5, description="难度")
    content: str = Field(..., description="题目内容")
    options: Optional[str] = Field(None, description="选项 JSON")
    answer: Optional[str] = Field(None, description="答案")
    analysis: Optional[str] = Field(None, description="解析")
    score: float = Field(5.0, description="分值")
    knowledge_points: str = Field("[]", description="知识点 JSON")


class BatchImportRequest(BaseModel):
    questions: list[BatchImportItem] = Field(..., description="题目列表")


class BatchImportResponse(BaseModel):
    imported: int = Field(..., description="成功导入数")
    failed: int = Field(..., description="失败数")
    errors: list[str] = Field(default_factory=list, description="错误详情")


class SmartComposeRequest(BaseModel):
    template_id: Optional[str] = Field(None, description="模板ID")
    subject: str = Field(..., description="学科")
    grade: str = Field(..., description="年级")
    difficulty: str = Field("medium", description="难度 easy/medium/hard")
    knowledge_points: list[str] = Field(default_factory=list, description="知识点")
    total_score: float = Field(100.0, description="总分")
    sections: Optional[str] = Field(None, description="题型配置 JSON")
    bank_ratio: float = Field(0.5, ge=0.0, le=1.0, description="从题库选题比例 0-1")


# ──────────────────────────────────────────────
# 题目质量统计 & 详情
# ──────────────────────────────────────────────

class QuestionQualityStats(BaseModel):
    """题库质量统计概览"""
    total_questions: int = 0
    quality_distribution: dict = Field(default_factory=dict, description="质量等级分布 {level: count}")
    avg_difficulty: float = 0
    avg_discrimination: float = 0
    knowledge_coverage: float = 0


class QuestionQualityDetail(BaseModel):
    """单题质量详情"""
    quality_score: Optional[float] = None
    quality_level: str = "normal"
    usage_count: int = 0
    avg_correct_rate: Optional[float] = None
    difficulty_calibrated: Optional[float] = None
    discrimination: Optional[float] = None
    calibration_history: list = Field(default_factory=list)


# ──────────────────────────────────────────────
# 学情分析
# ──────────────────────────────────────────────

class LearningProfileResponse(BaseModel):
    """班级学情画像"""
    class_id: str
    subject: str
    overall_mastery: float = 0
    knowledge_mastery: dict = Field(default_factory=dict)
    weak_points: list = Field(default_factory=list)
    strong_points: list = Field(default_factory=list)
    student_count: int = 0


class ClassReportResponse(BaseModel):
    """班级学习报告"""
    id: str
    class_id: str
    subject: str
    report_type: str
    report_date: str
    overall_mastery: Optional[float] = None
    knowledge_mastery: Optional[dict] = None
    weak_points: Optional[list] = None
    strong_points: Optional[list] = None
    recommendations: Optional[list] = None
    student_count: int = 0


# ──────────────────────────────────────────────
# 基于学情的智能组卷
# ──────────────────────────────────────────────

class SmartComposeByLearningRequest(BaseModel):
    """基于学情画像的智能组卷请求"""
    class_id: str = Field(..., description="班级ID")
    subject: str = Field(..., description="学科")
    knowledge_points: list = Field(default_factory=list, description="知识点列表")
    total_score: float = Field(100, description="总分")
    duration: int = Field(45, description="考试时长(分钟)")
    strategy: str = Field("learning_profile", description="组卷策略: learning_profile/weak_reinforce/balanced")
    difficulty_curve: str = Field("progressive", description="难度曲线: progressive/flat/inverted")
    bank_ratio: float = Field(0.5, ge=0.0, le=1.0, description="题库选题比例")
    sections: list = Field(default_factory=list, description="题型分段配置")
