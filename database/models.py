# database/models.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime, or_
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
    is_admin = Column(Boolean, default=False)
    
    # --- 사용자 상세 정보 ---
    position = Column(String(50)) # 직책
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
    materials = relationship("Material", back_populates="client")

class Material(Base):
    """원료 데이터 모델"""
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    unit_price = Column(Float, default=0.0)
    package_unit = Column(String(50))
    
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship("Client")
    
    manufacturer = Column(String(100))
    hs_code = Column(String(50))
    nmpa_reg_num = Column(String(100))
    reg_date = Column(String(20))
    is_active = Column(Boolean, default=True)

    change_log = Column(Text, nullable=True) # 변경 이력
    
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
    # target_client_id는 텍스트로 변경되었으므로, 아래 관계는 주석 처리하거나 삭제해야 합니다.
    target_client_id = Column(Integer, ForeignKey('clients.id'))
    target_client = relationship("Client", foreign_keys=[target_client_id])
    
    # OEM/ODM 정보
    oem_odm_client_id = Column(Integer, ForeignKey('clients.id'))
    oem_odm_client = relationship("Client", foreign_keys=[oem_odm_client_id])

    change_log = Column(Text, nullable=True) # 변경 이력을 저장할 컬럼

    sample_sent_count = Column(Integer, default=0) # 샘플 발송 횟수
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
