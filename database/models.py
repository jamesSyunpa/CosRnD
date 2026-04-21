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
