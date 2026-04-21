# database/models.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime, or_, Date
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    """
    사용자 정보를 저장하는 테이블 모델
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(255), nullable=False) # 해시된 비밀번호 저장
    real_name = Column(String(50)) # 사용자의 실제 이름
    is_admin = Column(Boolean, default=False)  # 하위 호환성을 위해 유지
    
    # --- 권한 관리 ---
    # QC: 품질관리원, RD: 연구원, RQ: 연구/품질 통합관리자, 
    # RQD: 연구/품질/데이터 관리자, MSAD: 모든 관리자
    role = Column(String(20), default='RD')  # 기본값은 연구원
    
    # --- 사용자 상세 정보 ---
    position = Column(String(50)) # 직책
    manager_code = Column(String(50), unique=True, nullable=True) # 담당번호 (NULL 허용)
    contact = Column(String(20)) # 연락처
    zip_code = Column(String(10)) # 우편번호
    address = Column(String(255)) # 주소
    
    change_log = Column(Text, nullable=True) # 변경 이력
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # --- 사용자 편의 기능 설정 ---
    remember_id = Column(Boolean, default=False)
    auto_login = Column(Boolean, default=False)

    def __repr__(self):
        return f'<User {self.username}>'
    
    # 권한 확인 헬퍼 메서드 - 새로운 권한 체계
    def has_quality_access(self):
        """품질관리 서류 접근 권한 (원료목록보고, COA, MSDS, 제품표준서, 제조관리기록서)"""
        return bool(self.is_admin) or self.role in ['QC', 'RQ', 'RQD', 'MSAD']
    
    def has_research_access(self):
        """연구 서류 접근 권한 (처방, 견적, 전성분, 물성치/SPEC, 기능성보고/참고자료)"""
        return bool(self.is_admin) or self.role in ['RD', 'RQ', 'RQD', 'MSAD']
    
    def can_view_material_data(self):
        """성분 데이터 조회 권한 - RD는 검색/참고만"""
        return bool(self.is_admin) or self.role in ['RD', 'RQ', 'RQD', 'MSAD']
    
    def can_edit_material_data(self):
        """성분 데이터 편집 권한 - RQD, MSAD만 가능"""
        return bool(self.is_admin) or self.role in ['RQD', 'MSAD']
    
    def can_view_client_data(self):
        """거래처 데이터 조회 권한 - QC, RD는 검색/참고만"""
        return bool(self.is_admin) or self.role in ['QC', 'RD', 'RQ', 'RQD', 'MSAD']
    
    def can_edit_client_data(self):
        """거래처 데이터 편집 권한 - RQD, MSAD만 가능"""
        return bool(self.is_admin) or self.role in ['RQD', 'MSAD']
    
    def can_access_data_management(self):
        """데이터관리 메뉴 접근 권한 - 모든 권한이 접근 가능"""
        return True if self.is_admin else self.role in ['QC', 'RD', 'RQ', 'RQD', 'MSAD']
    
    def can_manage_all_data(self):
        """모든 데이터 관리 권한 (수정, 삭제 등) - RQD, MSAD"""
        return bool(self.is_admin) or self.role in ['RQD', 'MSAD']
    
    def can_delete(self):
        """삭제 승인 권한 - RQD, MSAD"""
        return bool(self.is_admin) or self.role in ['RQD', 'MSAD']
    
    def is_master_admin(self):
        """최고 관리자 권한 (백업 기능 포함)"""
        # 정책 변경: RQD도 마스터 권한을 모두 포함
        return bool(self.is_admin) or self.role in ['MSAD', 'RQD']
    
    def has_backup_authority(self):
        """데이터 삭제 전 마스터 백업 권한"""
        # 정책 변경: RQD도 백업 권한 포함
        return bool(self.is_admin) or self.role in ['MSAD', 'RQD']
    
    def can_delete_formulation(self):
        """처방 삭제 권한 - 연구원 이상(RD, RQ, RQD, MSAD)"""
        return bool(self.is_admin) or self.role in ['RD', 'RQ', 'RQD', 'MSAD']
    
class Client(Base):
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # 거래처명
    business_number = Column(String(20))        # 사업자번호
    client_type = Column(String(50))            # 거래처 유형 (예: '원료', 'OEM/ODM', '부자재')
    
    # --- 상세 정보 ---
    ceo_name = Column(String(50))               # 대표자명
    manager_name = Column(String(50))           # 담당자명
    fax = Column(String(20))                    # 팩스번호
    zip_code = Column(String(10))               # 우편번호

    phone = Column(String(20))                  # 전화번호
    email = Column(String(100))                 # 이메일
    address = Column(Text)                      # 주소
    is_active = Column(Boolean, default=True)   # 활성화 여부

    change_log = Column(Text, nullable=True) # 변경 이력
    created_at = Column(DateTime, default=datetime.utcnow)  # 생성일시
    
    # 관계 설정
    materials_as_supplier = relationship("Material", back_populates="supplier", foreign_keys="Material.supplier_id")

class Material(Base):
    """원료 데이터 모델"""
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    name_en = Column(String(255)) # 영문원료명 추가
    origin = Column(String(100)) # 원산지 추가
    unit_price = Column(Float, default=0.0)
    package_unit = Column(String(50))
    
    supplier_id = Column(Integer, ForeignKey('clients.id'))
    supplier = relationship("Client", back_populates="materials_as_supplier", foreign_keys=[supplier_id])
    
    manufacturer = Column(String(100))
    hs_code = Column(String(50))
    nmpa_reg_num = Column(String(100))
    reg_date = Column(String(20))
    is_active = Column(Boolean, default=True)

    change_log = Column(Text, nullable=True) # 변경 이력
    # 수정일과 생성일 추가
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ingredient와의 관계 설정
    ingredients = relationship("Ingredient", back_populates="material", cascade="all, delete-orphan")

class Ingredient(Base):
    """전성분 정보 모델 (하나의 원료에 여러개 포함)"""
    __tablename__ = 'ingredients'
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)
    
    name_ko = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=False)
    cas_no = Column(String(50))
    composition_ratio = Column(Float)
    function = Column(String(100))
    ewg_grade = Column(String(10))
    ewg_data = Column(Text)
    # 2024-07-26: HS CODE, NMPA, 비고 필드 추가
    hs_code = Column(String(50))
    nmpa_reg_num = Column(String(100))
    remark = Column(Text)

    # Material과의 관계 설정
    material = relationship("Material", back_populates="ingredients")

class Formulation(Base):
    """처방 정보 모델"""
    __tablename__ = 'formulations'
    id = Column(Integer, primary_key=True)
    
    # 본 실험 처방 정보
    experiment_name = Column(String(255), nullable=False)
    experiment_date = Column(String(20))
    manager_name = Column(String(50))
    manager_code = Column(String(50)) # 담당번호 (구 unique_code)
    lab_no = Column(String(50)) # LAB NO.
    revision = Column(String(50))
    experiment_ph_initial = Column(String(20))
    experiment_ph_next_day = Column(String(20))
    experiment_viscosity_initial = Column(String(20))
    experiment_viscosity_next_day = Column(String(20))
    experiment_machine = Column(String(255))
    
    experiment_comment = Column(Text) # 품평결과 및 특이사항
    # 타겟 정보
    has_target_info = Column(Boolean, default=False)
    target_sample_name = Column(String(255))
    target_ph_initial = Column(String(20))
    target_ph_next_day = Column(String(20))
    target_viscosity_initial = Column(String(20))
    target_viscosity_next_day = Column(String(20))
    target_machine = Column(String(255))

    # 타겟 거래처 정보
    # 2024-07-29: 타겟 거래처는 ID가 아닌 텍스트로 저장되므로 String으로 변경하고 외래 키 제약 제거
    target_client_id = Column(String(255))
    
    # OEM/ODM 정보
    oem_odm_client_id = Column(Integer, ForeignKey('clients.id'))
    oem_odm_client = relationship("Client", foreign_keys=[oem_odm_client_id])

    change_log = Column(Text, nullable=True) # 변경 이력을 저장할 컬럼

    sample_sent_count = Column(Integer, default=0) # 샘플 발송 횟수
    sample_delivery_date = Column(Date) # 샘플 발송일
    
    # 삭제 플래그 (소프트 삭제)
    is_deleted = Column(Boolean, default=False)
    
    # 구성 원료 관계
    # cascade="all, delete-orphan": Formulation이 삭제될 때 관련된 모든 FormulationItem도 함께 삭제되도록 설정합니다.
    # passive_deletes=True: 데이터베이스의 ON DELETE CASCADE 기능을 사용하도록 SQLAlchemy에 지시합니다.
    items = relationship("FormulationItem", back_populates="formulation",
                         cascade="all, delete-orphan", passive_deletes=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class FormulationItem(Base):
    """처방 구성 원료 정보 모델"""
    __tablename__ = 'formulation_items'
    id = Column(Integer, primary_key=True)
    
    # ondelete='CASCADE' : 부모인 Formulation이 삭제될 때 DB 레벨에서 함께 삭제되도록 설정합니다.
    formulation_id = Column(Integer, ForeignKey('formulations.id', ondelete='CASCADE'), nullable=False)
    material_id = Column(Integer, ForeignKey('materials.id')) # 구분선은 material_id가 없을 수 있음
    
    # 처방 내에서의 정보
    order = Column(Integer) # 순서
    phase = Column(String(20)) # 구분
    material_code = Column(String(50))
    material_name = Column(String(255))
    ratio = Column(Float)
    amount = Column(Float)
    
    formulation = relationship("Formulation", back_populates="items")
    material = relationship("Material") # material_id가 NULL일 수 있으므로 outer join

# ---------------------------------------------------------------------------
# 생산 처방 (확정 레시피)
# ---------------------------------------------------------------------------

class ProductionFormulation(Base):
    __tablename__ = 'production_formulations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_formulation_id = Column(Integer, ForeignKey('formulations.id'), nullable=False)
    product_name = Column(String(255), nullable=False)
    production_code = Column(String(50))  # 생산코드 (LAB NO.는 참고용)
    lab_no = Column(String(50))
    revision = Column(String(50))
    base_weight_g = Column(Float)  # 기준 중량(g)
    status = Column(String(50), default='확정')  # 상태: 초안/검토중/확정 등
    effective_date = Column(Date)
    approved_by_user_id = Column(Integer, ForeignKey('users.id'))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 레시피 스냅샷(JSON): order, phase, code, name, ratio, amount 등 고정 저장
    items_snapshot = Column(Text)

    # 관계
    source_formulation = relationship('Formulation')
    approved_by = relationship('User')
    # 단계(공정) 관계
    steps = relationship('ProductionStep', back_populates='production', cascade='all, delete-orphan', order_by='ProductionStep.step_no')

class ProductionStep(Base):
    __tablename__ = 'production_steps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    production_formulation_id = Column(Integer, ForeignKey('production_formulations.id', ondelete='CASCADE'), nullable=False)
    step_no = Column(Integer)  # 단계 번호
    phase = Column(String(50))  # 구분(Phase)
    instruction = Column(Text)  # 작업 지시/절차
    temperature = Column(String(50))  # 온도(예: 70~75℃)
    time_min = Column(Float)  # 시간(분)
    rpm = Column(String(50))  # 교반 속도 또는 범위
    equipment = Column(String(255))  # 장비/용기
    notes = Column(Text)  # 비고
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    production = relationship('ProductionFormulation', back_populates='steps')

class ProductionRun(Base):
    __tablename__ = 'production_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    production_formulation_id = Column(Integer, ForeignKey('production_formulations.id', ondelete='CASCADE'), nullable=False)
    run_date = Column(Date)
    lot_no = Column(String(100))
    quantity_g = Column(Float)
    notes = Column(Text)
    
    # 물성치 필드 추가
    specific_gravity = Column(String(50))  # 비중
    viscosity_initial = Column(String(50))  # 점도(당일)
    viscosity_next_day = Column(String(50))  # 점도(익일)
    ph_initial = Column(String(50))  # pH(당일)
    ph_next_day = Column(String(50))  # pH(익일)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    production = relationship('ProductionFormulation')

# ----------------------------------------------------------------------------
# 품질관리 저장용 테이블들 (원료목록보고, 반제품/완제품 COA)
# ----------------------------------------------------------------------------


class IngredientReport(Base):
    __tablename__ = 'ingredient_reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(255), nullable=False)
    manufacturer = Column(String(255))
    type_code = Column(String(100))  # 유형
    functional_type_code = Column(String(100))  # 기능성 유형
    functional_code = Column(String(100))  # 기능성 코드
    usage = Column(String(255))  # 용도
    custom_content = Column(Text)  # 자율기재사항
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship('IngredientReportItem', back_populates='report', cascade='all, delete-orphan')


class IngredientReportItem(Base):
    __tablename__ = 'ingredient_report_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('ingredient_reports.id', ondelete='CASCADE'), nullable=False)
    row_no = Column(Integer)
    ingredient_name = Column(String(255), nullable=False)

    report = relationship('IngredientReport', back_populates='items')


class SemiFinishedCOA(Base):
    __tablename__ = 'semi_finished_coa'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(255), nullable=False)
    lot_no = Column(String(100))
    manufacture_date = Column(Date)
    test_date = Column(Date)
    examiner = Column(String(100))  # 시험자
    overall_result = Column(String(100))  # 종합판정
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship('SemiFinishedCOAItem', back_populates='header', cascade='all, delete-orphan')


class SemiFinishedCOAItem(Base):
    __tablename__ = 'semi_finished_coa_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    header_id = Column(Integer, ForeignKey('semi_finished_coa.id', ondelete='CASCADE'), nullable=False)
    seq_no = Column(Integer)  # 번호
    item_name = Column(String(255))  # 시험항목
    spec = Column(String(255))  # 시험기준
    result = Column(String(255))  # 시험결과
    remark = Column(String(255))  # 비고

    header = relationship('SemiFinishedCOA', back_populates='items')


class FinishedProductCOA(Base):
    __tablename__ = 'finished_product_coa'

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(255), nullable=False)
    semi_mfg_date = Column(Date)  # 반제품 제조일자
    semi_lot_no = Column(String(100))  # 반제품 제조번호
    pack_date = Column(Date)  # 포장일자
    finished_lot_no = Column(String(100))  # 완제품 제조번호
    expiry_date = Column(Date)  # 유통기한
    unit_volume_ml = Column(Float)  # 용량(ml)
    sampling_method = Column(String(255))  # 검체채취방법
    test_date = Column(Date)
    examiner = Column(String(100))
    reviewer = Column(String(100))  # 확인자
    overall_result = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship('FinishedProductCOAItem', back_populates='header', cascade='all, delete-orphan')


class FinishedProductCOAItem(Base):
    __tablename__ = 'finished_product_coa_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    header_id = Column(Integer, ForeignKey('finished_product_coa.id', ondelete='CASCADE'), nullable=False)
    item_id = Column(String(50))  # 항목 ID (예: 1~7 또는 '특이사항')
    item_name = Column(String(255))  # 항목명
    spec = Column(String(255))  # 시험기준
    result = Column(String(255))  # 시험결과
    note = Column(String(255))  # 비고/특이사항

    header = relationship('FinishedProductCOA', back_populates='items')

# ---------------------------------------------------------------------------
# 통합 문서 패키지 (생산 처방 관련 자료 일괄 저장)
# ---------------------------------------------------------------------------

class DocumentPackage(Base):
    __tablename__ = 'document_packages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    formulation_id = Column(Integer, ForeignKey('formulations.id'), nullable=True)
    production_formulation_id = Column(Integer, ForeignKey('production_formulations.id'), nullable=True)
    product_name = Column(String(255))
    revision = Column(String(50))
    created_by_user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text)

    # 스냅샷(JSON 문자열) 저장: 전성분/견적 등 구조화 데이터를 Text로 저장
    ingredient_snapshot = Column(Text)   # 모든 전성분 뷰의 내용 스냅샷(JSON)
    quotation_snapshot = Column(Text)    # 견적 상세 스냅샷(JSON)

    # 관계
    formulation = relationship('Formulation')
    production_formulation = relationship('ProductionFormulation')
    created_by = relationship('User')
    links = relationship('DocumentPackageLink', back_populates='package', cascade='all, delete-orphan')
    attachments = relationship('DocumentAttachment', back_populates='package', cascade='all, delete-orphan')

class DocumentPackageLink(Base):
    __tablename__ = 'document_package_links'

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey('document_packages.id', ondelete='CASCADE'), nullable=False)
    doc_type = Column(String(50), nullable=False)  # 예: 'IngredientReport', 'SemiFinishedCOA', 'FinishedProductCOA', 'SPEC'
    ref_id = Column(Integer, nullable=False)       # 참조 테이블의 PK

    package = relationship('DocumentPackage', back_populates='links')

class DocumentAttachment(Base):
    __tablename__ = 'document_attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(Integer, ForeignKey('document_packages.id', ondelete='CASCADE'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    attachment_type = Column(String(50))  # 예: 'MSDS', 'SPEC', 'OTHER'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    package = relationship('DocumentPackage', back_populates='attachments')
