import sys
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QCompleter, QLineEdit,
    QMessageBox, QTabWidget, QInputDialog, QMenuBar, QAction
)
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt, QStringListModel
from PyQt5.QtGui import QColor, QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.font_manager as fm
import json
import os

# Matplotlib 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 8

# 제형 조정 함수
def adjust_formulation_with_phase(formulation):
    water = formulation['water_ratio']
    oil = formulation['oil_ratio']
    emulsifier = formulation['emulsifier_ratio']
    phase = formulation.get('emulsifier_phase', 'water')

    total = water + oil + emulsifier
    if abs(total - 1.0) > 0.005:
        raise ValueError(f"비율 합계가 100%가 아닙니다: {total*100:.1f}%")

    if phase == 'water' and water < emulsifier:
        raise ValueError("수상 비율이 유화제 비율보다 작습니다.")
    if phase == 'oil' and oil < emulsifier:
        raise ValueError("유상 비율이 유화제 비율보다 작습니다.")

    return {
        "water_ratio": round(water, 4),
        "oil_ratio": round(oil, 4),
        "emulsifier_ratio": round(emulsifier, 4)
    }

# 제형 타입 정의
FORMULATION_TYPES = {
    "클렌징오일": {
        "hlb_range": (1, 4),
        "water_ratio": 0.095,
        "oil_ratio": 0.855,
        "emulsifier_ratio": 0.05,
        "type": "W/O"
    },
    "W/O 크림": {
        "hlb_range": (3, 6),
        "water_ratio": 0.294,
        "oil_ratio": 0.686,
        "emulsifier_ratio": 0.02,
        "type": "W/O"
    },
    "연고": {
        "hlb_range": (3, 5),
        "water_ratio": 0.198,
        "oil_ratio": 0.792,
        "emulsifier_ratio": 0.01,
        "type": "W/O"
    },
    "선크림": {
        "hlb_range": (4, 6),
        "water_ratio": 0.291,
        "oil_ratio": 0.679,
        "emulsifier_ratio": 0.03,
        "type": "W/O"
    },
    "로션": {
        "hlb_range": (8, 10),
        "water_ratio": 0.672,
        "oil_ratio": 0.288,
        "emulsifier_ratio": 0.04,
        "type": "O/W"
    },
    "O/W 크림": {
        "hlb_range": (9, 12),
        "water_ratio": 0.57,
        "oil_ratio": 0.38,
        "emulsifier_ratio": 0.05,
        "type": "O/W"
    },
    "세럼": {
        "hlb_range": (10, 13),
        "water_ratio": 0.772,
        "oil_ratio": 0.193,
        "emulsifier_ratio": 0.035,
        "type": "O/W"
    },
    "클렌징밀크": {
        "hlb_range": (12, 14),
        "water_ratio": 0.672,
        "oil_ratio": 0.288,
        "emulsifier_ratio": 0.04,
        "type": "O/W"
    },
    "세정제": {
        "hlb_range": (13, 15),
        "water_ratio": 0.8865,
        "oil_ratio": 0.0985,
        "emulsifier_ratio": 0.015,
        "type": "S/W"
    },
    "에센스": {
        "hlb_range": (15, 18),
        "water_ratio": 0.9405,
        "oil_ratio": 0.0495,
        "emulsifier_ratio": 0.01,
        "type": "O/W"
    },
    "토너": {
        "hlb_range": (18, 20),
        "water_ratio": 0.9751,
        "oil_ratio": 0.0249,
        "emulsifier_ratio": 0.005,
        "type": "O/W"
    },
}

# 성분 타입 추론
def infer_type(name, code):
    try:
        code = int(code)
    except (ValueError, TypeError):
        return "기타"
    
    if 1000 <= code < 2000 or code == 9001:
        return "물"
    elif 2000 <= code < 3000:
        return "파우더"
    elif 3000 <= code < 4000:
        return "오일"
    elif 4000 <= code < 5000:
        return "에센셜오일"
    elif 5000 <= code < 6000:
        return "보존제"
    elif 6000 <= code < 7000:
        return "점증제"
    elif 7000 <= code < 8000:
        return "물"
    elif 8000 <= code < 9000:
        return "유화제"
    elif isinstance(code, str) and code.lower().startswith("new"):
        return "신규원료"
    else:
        return "기타"

# 유화제 조합 제안
def suggest_emulsifier_blend(target_hlb, hlb_df, max_combinations=3):
    emulsifiers = hlb_df[hlb_df["INGREDIENT"].str.contains("emulsifier", case=False, na=False)]
    if emulsifiers.empty:
        return []
    
    suggestions = []
    for i, row1 in emulsifiers.iterrows():
        for j, row2 in emulsifiers.iterrows():
            if i >= j:
                continue
            hlb1, hlb2 = row1["HLB"], row2["HLB"]
            for ratio in np.arange(0.1, 0.91, 0.1):
                combined_hlb = hlb1 * ratio + hlb2 * (1 - ratio)
                if abs(combined_hlb - target_hlb) < 0.5:
                    suggestions.append({
                        "emulsifier1": row1["INGREDIENT"],
                        "emulsifier2": row2["INGREDIENT"],
                        "ratio": round(ratio, 2),
                        "combined_hlb": round(combined_hlb, 2)
                    })
                    if len(suggestions) >= max_combinations:
                        return suggestions
    return suggestions

class HLBDesigner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HLB 제형 설계기")
        self.resize(1200, 800)
        self.history = []
        self.redo_stack = []

        # 데이터 로드
        try:
            self.df = pd.read_excel("data_ing.xls")
            self.df.columns = self.df.columns.str.replace(r'\n|\(|\)', '', regex=True)
            self.df["INGREDIENT"] = self.df["INGREDIENT300"].astype(str).str.strip()
            # 디버깅: 열 이름 출력
        except FileNotFoundError:
            QMessageBox.critical(self, "오류", "data_ing.xls 파일을 찾을 수 없습니다!")
            sys.exit(1)
        except KeyError as e:
            QMessageBox.critical(self, "오류", f"데이터프레임 열 오류: {str(e)}")
            sys.exit(1)

        try:
            self.hlb_df = pd.read_excel("hlb값.xlsx", header=None, names=["INGREDIENT", "HLB"])
            self.hlb_df["INGREDIENT"] = self.hlb_df["INGREDIENT"].str.strip()
            self.hlb_df["HLB"] = pd.to_numeric(self.hlb_df["HLB"], errors='coerce')
        except FileNotFoundError:
            QMessageBox.critical(self, "오류", "hlb값.xlsx 파일을 찾을 수 없습니다!")
            sys.exit(1)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # 메뉴 바
        menubar = QMenuBar()
        file_menu = menubar.addMenu("파일")
        save_action = QAction("제형 저장", self)
        save_action.triggered.connect(self.save_formulation)
        file_menu.addAction(save_action)
        load_action = QAction("제형 불러오기", self)
        load_action.triggered.connect(self.load_formulation)
        file_menu.addAction(load_action)
        main_layout.setMenuBar(menubar)

        # 탭 구성
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # 제형 설계 탭
        formulation_widget = QWidget()
        formulation_layout = QVBoxLayout()
        formulation_widget.setLayout(formulation_layout)
        tabs.addTab(formulation_widget, "제형 설계")

        # 제형 선택
        form_layout = QHBoxLayout()
        form_label = QLabel("제형 선택:")
        form_label.setFont(QFont("맑은 고딕", 10))
        form_layout.addWidget(form_label)
        self.form_type = QComboBox()
        self.form_type.addItems(FORMULATION_TYPES.keys())
        self.form_type.currentTextChanged.connect(self.update_form_info)
        form_layout.addWidget(self.form_type)
        formulation_layout.addLayout(form_layout)

        # 제형 정보 및 시각화
        info_vis_layout = QHBoxLayout()
        self.form_info_text = QTextEdit()
        self.form_info_text.setMaximumHeight(100)
        self.form_info_text.setReadOnly(True)
        self.form_info_text.setFont(QFont("맑은 고딕", 9))
        info_vis_layout.addWidget(self.form_info_text)

        # 시각화 캔버스
        self.figure, self.ax = plt.subplots(figsize=(6, 1.2))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setFixedSize(400, 100)
        info_vis_layout.addWidget(self.canvas)
        formulation_layout.addLayout(info_vis_layout)

        # 성분 테이블
        self.table = QTableWidget(10, 6)
        self.table.setHorizontalHeaderLabels(["코드", "성분명", "타입", "함량(%)", "HLB", "비고"])
        self.table.cellChanged.connect(self.handle_cell_changed)
        self.table.setFont(QFont("맑은 고딕", 9))
        formulation_layout.addWidget(self.table)

        # 버튼
        button_layout = QHBoxLayout()
        self.add_row_button = QPushButton("행 추가")
        self.add_row_button.clicked.connect(self.add_row)
        button_layout.addWidget(self.add_row_button)

        self.remove_row_button = QPushButton("행 삭제")
        self.remove_row_button.clicked.connect(self.remove_row)
        button_layout.addWidget(self.remove_row_button)

        self.undo_button = QPushButton("실행 취소")
        self.undo_button.clicked.connect(self.undo)
        button_layout.addWidget(self.undo_button)

        self.redo_button = QPushButton("다시 실행")
        self.redo_button.clicked.connect(self.redo)
        button_layout.addWidget(self.redo_button)

        self.reset_button = QPushButton("초기화")
        self.reset_button.clicked.connect(self.reset_table_and_result)
        button_layout.addWidget(self.reset_button)

        self.calc_btn = QPushButton("HLB 계산")
        self.calc_btn.clicked.connect(self.calculate_hlb)
        button_layout.addWidget(self.calc_btn)

        self.suggest_btn = QPushButton("유화제 추천")
        self.suggest_btn.clicked.connect(self.suggest_emulsifiers)
        button_layout.addWidget(self.suggest_btn)
        formulation_layout.addLayout(button_layout)

        # 결과 텍스트
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("맑은 고딕", 9))
        formulation_layout.addWidget(self.result_text)

        # 성분 관리 탭
        ingredient_widget = QWidget()
        ingredient_layout = QVBoxLayout()
        ingredient_widget.setLayout(ingredient_layout)
        tabs.addTab(ingredient_widget, "성분 관리")

        self.ingredient_table = QTableWidget(5, 3)
        self.ingredient_table.setHorizontalHeaderLabels(["성분명", "HLB", "비고"])
        self.ingredient_table.setFont(QFont("맑은 고딕", 9))
        ingredient_layout.addWidget(self.ingredient_table)

        ingredient_button_layout = QHBoxLayout()
        self.add_ing_btn = QPushButton("성분 추가")
        self.add_ing_btn.clicked.connect(self.add_ingredient)
        ingredient_button_layout.addWidget(self.add_ing_btn)
        ingredient_layout.addLayout(ingredient_button_layout)

        self.setLayout(main_layout)
        self.setup_autocomplete()
        self.update_form_info()
        self.save_state()

    def save_state(self):
        state = {
            "table_data": [
                [self.table.item(r, c).text() if self.table.item(r, c) else ""
                 for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())
            ],
            "form_type": self.form_type.currentText(),
            "result_text": self.result_text.toPlainText()
        }
        self.history.append(state)
        self.redo_stack.clear()

    def undo(self):
        if len(self.history) <= 1:
            return
        current_state = self.history.pop()
        self.redo_stack.append(current_state)
        state = self.history[-1]
        self.restore_state(state)

    def redo(self):
        if not self.redo_stack:
            return
        state = self.redo_stack.pop()
        self.history.append(state)
        self.restore_state(state)

    def restore_state(self, state):
        self.table.setRowCount(len(state["table_data"]))
        for r, row in enumerate(state["table_data"]):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(value))
        self.form_type.setCurrentText(state["form_type"])
        self.result_text.setText(state["result_text"])
        self.setup_autocomplete()

    def add_row(self):
        self.table.insertRow(self.table.rowCount())
        self.setup_autocomplete()
        self.save_state()

    def remove_row(self):
        if self.table.rowCount() > 1:
            self.table.removeRow(self.table.rowCount() - 1)
            self.save_state()

    def reset_table_and_result(self):
        self.table.setRowCount(10)
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                self.table.setItem(row, col, QTableWidgetItem(""))
        self.result_text.clear()
        self.setup_autocomplete()
        self.update_visualization([])
        self.save_state()

    def update_form_info(self):
        form = self.form_type.currentText()
        form_data = FORMULATION_TYPES.get(form, {})
        if form_data:
            try:
                adjusted = adjust_formulation_with_phase(form_data.copy())
                form_info = (
                    f"제형: {form}\n"
                    f"권장 HLB 범위: {form_data['hlb_range'][0]} ~ {form_data['hlb_range'][1]}\n"
                    f"수상 비율: {adjusted['water_ratio'] * 100:.1f}%\n"
                    f"유상 비율: {adjusted['oil_ratio'] * 100:.1f}%\n"
                    f"유화제 비율: {adjusted['emulsifier_ratio'] * 100:.1f}%\n"
                )
                self.form_info_text.setText(form_info)
                data = [
                    ("수상", adjusted["water_ratio"] * 100),
                    ("유상", adjusted["oil_ratio"] * 100),
                    ("유화제", adjusted["emulsifier_ratio"] * 100)
                ]
                self.update_visualization(data, form_type=form_data["type"])
            except ValueError as e:
                self.form_info_text.setText(f"오류: {str(e)}")

    def update_visualization(self, data, form_type="O/W"):
        self.ax.clear()
        if data:
            # 데이터 딕셔너리로 변환
            data_dict = {label: value for label, value in data}
            # 0% 항목 제외
            filtered_data = [(l, v) for l, v in data_dict.items() if v > 0]
            if filtered_data:
                # 제형 타입에 따른 순서 설정
                if form_type in ["O/W", "S/W"]:
                    order = ["수상", "유화제", "유상", "기타"]
                else:  # W/O, W/S
                    order = ["유상", "유화제", "수상", "기타"]
                
                # 순서에 따라 정렬
                labels = []
                sizes = []
                for label in order:
                    if label in data_dict and data_dict[label] > 0:
                        labels.append(label)
                        sizes.append(data_dict[label])
                
                # # 색상 매핑 (더 진한 색상)
                # color_map = {
                #     "수상": '#4FC3F7',   # 진한 파랑
                #     "유상": '#4CAF50',   # 진한 초록
                #     "유화제": '#FF8A65', # 진한 주황
                #     "기타": '#B0BEC5'    # 진한 회색
                # }
                
                color_map = {
                    "수상": '#AED6F1',   # 파랑
                    "유상": '#A9DFBF',   # 초록
                    "유화제": '#F5B7B1', # 주황
                    "기타": '#D5DBDB'    # 회색
                }
                
                colors = [color_map[label] for label in labels]
                
                # 누적 막대그래프
                left = 0
                tick_positions = []
                tick_labels = []
                for label, size, color in zip(labels, sizes, colors):
                    self.ax.barh(0, size, left=left, color=color, height=0.4, edgecolor='black', linewidth=0.5)
                    # X축 눈금 위치와 레이블 준비
                    tick_positions.append(left + size/2)
                    tick_labels.append(f'{label}({size:.1f}%)')
                    left += size
                
                # X축 설정
                self.ax.set_xlim(0, 100)
                self.ax.set_xticks(tick_positions)
                self.ax.set_xticklabels(tick_labels, fontsize=7, rotation=0, ha='center')
                self.ax.tick_params(axis='x', length=0)  # 눈금 선 제거
                
                # Y축 및 그래프 설정
                self.ax.set_ylim(-0.5, 0.5)
                self.ax.set_yticks([])
                self.ax.set_xlabel('')
                self.ax.set_title('제형 비율')
                self.ax.grid(True, axis='x', linestyle='--', alpha=0.7)
        
        self.figure.tight_layout(pad=0.5)
        self.canvas.draw()

    def setup_autocomplete(self):
        try:
            # 데이터프레임에서 성분 리스트 가져오기
            if "INGREDIENT" not in self.df.columns:
                raise KeyError("INGREDIENT 열이 없습니다.")
                
            ingredients = self.df["INGREDIENT"].dropna().astype(str).tolist()
            ingredients = [ing for ing in ingredients if ing.strip()]  # 빈 문자열 제거
            ingredients.sort(key=len)
            
            if not ingredients:
                print("경고: 성분 목록이 비어있습니다.")
                return
                
            model = QStringListModel(ingredients)
            max_width = max([len(str(ing)) for ing in ingredients]) * 7

            for row in range(self.table.rowCount()):
                # 기존 아이템 텍스트 저장
                existing_text = ""
                existing_item = self.table.item(row, 1)
                if existing_item:
                    existing_text = existing_item.text()
                    
                # 이미 있는 셀 위젯 제거
                self.table.removeCellWidget(row, 1)
                
                # 새 LineEdit 생성
                line_edit = QLineEdit()
                if existing_text:
                    line_edit.setText(existing_text)
                    
                # 자동완성 설정
                completer = QCompleter()
                completer.setModel(model)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                completer.setFilterMode(Qt.MatchContains)
                
                popup = completer.popup()
                popup.setMinimumWidth(max(300, min(max_width, 800)))
                line_edit.setCompleter(completer)
                
                # 이벤트 연결 (lambda 대신 부분 함수 사용)
                from functools import partial
                line_edit.editingFinished.connect(partial(self.fill_from_lineedit, row, line_edit))
                
                # 테이블에 위젯 설정
                self.table.setCellWidget(row, 1, line_edit)
                
        except KeyError as e:
            QMessageBox.critical(self, "오류", f"자동완성 설정 중 오류: 열 '{e}'이(가) 없습니다.")
            print("사용 가능한 열:", list(self.df.columns))
        except Exception as e:
            print(f"setup_autocomplete 오류: {str(e)}")

    def fill_from_lineedit(self, row, line_edit):
        try:
            if not line_edit or not isinstance(line_edit, QLineEdit):
                return

            # 시그널 일시 해제
            try:
                line_edit.editingFinished.disconnect()
            except Exception:
                pass  # 이미 연결 안되어 있으면 무시

            name = line_edit.text().strip()

            if not name:
                self.table.setItem(row, 0, QTableWidgetItem(''))
                self.table.removeCellWidget(row, 1)
                self.table.setItem(row, 1, QTableWidgetItem(''))
                self.table.setItem(row, 2, QTableWidgetItem(''))
                self.table.setItem(row, 4, QTableWidgetItem(''))
                self.table.setItem(row, 5, QTableWidgetItem(''))
                return

            # 성분 이름으로 검색
            ingredient_row = self.df[self.df["INGREDIENT"].str.strip().str.lower() == name.lower()]
            if not ingredient_row.empty:
                code = str(ingredient_row.iloc[0]["코드"]) if "코드" in ingredient_row.columns else ""
                self.table.setItem(row, 0, QTableWidgetItem(code))
                self.table.removeCellWidget(row, 1)
                self.table.setItem(row, 1, QTableWidgetItem(name))

                type_value = infer_type(name, code) if code else "기타"
                self.table.setItem(row, 2, QTableWidgetItem(type_value))

                hlb_row = self.hlb_df[self.hlb_df["INGREDIENT"].str.strip().str.lower() == name.lower()]
                if not hlb_row.empty:
                    hlb_value = str(hlb_row["HLB"].values[0])
                    self.table.setItem(row, 4, QTableWidgetItem(hlb_value))
                else:
                    if type_value == "물":
                        self.table.setItem(row, 4, QTableWidgetItem("0"))
                    elif type_value in ["오일", "에센셜오일"]:
                        self.table.setItem(row, 4, QTableWidgetItem("7"))
                    else:
                        self.table.setItem(row, 4, QTableWidgetItem(''))
            else:
                self.table.setItem(row, 0, QTableWidgetItem(''))
                self.table.removeCellWidget(row, 1)
                self.table.setItem(row, 1, QTableWidgetItem(name))
                self.table.setItem(row, 2, QTableWidgetItem('기타'))
                self.table.setItem(row, 4, QTableWidgetItem(''))

            QApplication.processEvents()
            self.save_state()

        except RuntimeError as e:
            print(f"[위젯 처리 중 오류] {e}")
        except Exception as e:
            print(f"fill_from_lineedit 오류: {str(e)}")
            
    def handle_cell_changed(self, row, column):
        try:
            # 일단 시그널 차단
            self.table.blockSignals(True)

            # 여기서 setItem이나 기타 작업 수행
            item = self.table.item(row, column)
            if item:
                value = item.text().strip()
                # 예: 특정 컬럼에 따라 자동 값 채우기 등
                if column == 1 and value:
                    self.fill_from_lineedit(row, item)

            # 변경사항 저장 등 처리
            self.save_state()

        except Exception as e:
            print(f"[셀 변경 처리 중 오류] {str(e)}")

        finally:
            # 시그널 다시 허용
            self.table.blockSignals(False)

    def calculate_hlb(self):
        try:
            total_percent = 0
            weighted_hlb_all = 0
            water_total = oil_total = emulsifier_total = other_total = 0
            
            # 유상+유화제 계산용 변수
            oil_emul_total = 0
            oil_emul_weighted_hlb = 0
            
            invalid_rows = []

            for row in range(self.table.rowCount()):
                # 테이블에서 직접 아이템 가져오기
                name_item = self.table.item(row, 1)
                type_item = self.table.item(row, 2)
                percent_item = self.table.item(row, 3)
                hlb_item = self.table.item(row, 4)

                # 셀 위젯이 있는지 확인
                name_widget = self.table.cellWidget(row, 1)
                if name_widget and isinstance(name_widget, QLineEdit):
                    name = name_widget.text().strip()
                    # 위젯 내용을 테이블 아이템으로 변환
                    self.fill_from_lineedit(row, name_widget)
                    # 다시 아이템 가져오기
                    name_item = self.table.item(row, 1)
                    type_item = self.table.item(row, 2)
                    hlb_item = self.table.item(row, 4)

                # 필요한 데이터가 있는지 확인
                if not (name_item and name_item.text().strip() and
                        type_item and type_item.text().strip() and
                        percent_item and percent_item.text().strip() and
                        hlb_item and hlb_item.text().strip()):
                    continue

                try:
                    percent = float(percent_item.text())
                    hlb = float(hlb_item.text())
                    typ = type_item.text().strip()

                    if percent < 0:
                        raise ValueError("함량은 0 이상이어야 합니다.")

                    total_percent += percent
                    weighted_hlb_all += hlb * percent

                    if typ == "물":
                        water_total += percent
                    elif typ in ["오일", "에센셜오일"]:
                        oil_total += percent
                        oil_emul_total += percent
                        oil_emul_weighted_hlb += hlb * percent
                    elif typ == "유화제":
                        emulsifier_total += percent
                        oil_emul_total += percent
                        oil_emul_weighted_hlb += hlb * percent
                    else:
                        other_total += percent

                    percent_item.setBackground(QColor("white"))
                except ValueError as e:
                    invalid_rows.append(f"{row + 1}번 행: {str(e)}")
                    percent_item.setBackground(QColor("red"))

            if invalid_rows:
                self.result_text.setText("오류:\n" + "\n".join(invalid_rows))
                return

            if total_percent == 0:
                self.result_text.setText("유효한 성분 데이터를 입력해주세요.")
                return

            if abs(total_percent - 100) > 0.1:
                warning = f"경고: 총 함량이 100%가 아닙니다 (현재: {total_percent:.1f}%)\n"
            else:
                warning = ""

            # 전체 평균 HLB (디버그용)
            avg_hlb_all = weighted_hlb_all / total_percent if total_percent > 0 else 0
            
            # 유상+유화제 평균 HLB (실제 필요한 값)
            avg_hlb_oil_emul = oil_emul_weighted_hlb / oil_emul_total if oil_emul_total > 0 else 0
            
            form = self.form_type.currentText()
            form_data = FORMULATION_TYPES[form]
            
            result = f"{warning}선택 제형: {form}\n"
            result += f"유상+유화제 평균 HLB: {avg_hlb_oil_emul:.2f} (권장: {form_data['hlb_range'][0]} ~ {form_data['hlb_range'][1]})\n"
            result += f"전체 성분 평균 HLB: {avg_hlb_all:.2f} (참고값)\n\n"
            result += f"수상 비율: {water_total:.2f}% (권장: {form_data['water_ratio']*100:.1f}%)\n"
            result += f"유상 비율: {oil_total:.2f}% (권장: {form_data['oil_ratio']*100:.1f}%)\n"
            result += f"유화제 비율: {emulsifier_total:.2f}% (권장: {form_data['emulsifier_ratio']*100:.1f}%)\n"
            result += f"기타 비율: {other_total:.2f}%\n"

            # HLB 적합성 분석
            is_hlb_in_range = form_data['hlb_range'][0] <= avg_hlb_oil_emul <= form_data['hlb_range'][1]
            
            if not is_hlb_in_range:
                result += "\n⚠️ 경고: 유상+유화제 평균 HLB 값이 권장 범위를 벗어났습니다.\n"
                if avg_hlb_oil_emul < form_data['hlb_range'][0]:
                    result += f"  - HLB 값이 낮습니다. 더 높은 HLB 값을 가진 유화제를 추가하세요.\n"
                else:
                    result += f"  - HLB 값이 높습니다. 더 낮은 HLB 값을 가진 유화제를 추가하세요.\n"
            else:
                result += "\n✅ 유상+유화제 평균 HLB 값이 권장 범위 내에 있습니다.\n"

            # 비율 적합성 분석
            diff_water = form_data['water_ratio']*100 - water_total
            diff_oil = form_data['oil_ratio']*100 - oil_total
            diff_emulsifier = form_data['emulsifier_ratio']*100 - emulsifier_total

            result += f"\n비율 조정 제안:\n"
            if abs(diff_water) > 1:
                result += f"- 수상 비율을 {('늘려주세요' if diff_water > 0 else '줄여주세요')}: {abs(diff_water):.1f}%\n"
            if abs(diff_oil) > 1:
                result += f"- 유상 비율을 {('늘려주세요' if diff_oil > 0 else '줄여주세요')}: {abs(diff_oil):.1f}%\n"
            if abs(diff_emulsifier) > 0.5:
                result += f"- 유화제 비율을 {('늘려주세요' if diff_emulsifier > 0 else '줄여주세요')}: {abs(diff_emulsifier):.1f}%\n"

            # 결과 표시
            self.result_text.setText(result)
            
            # 시각화 업데이트
            data = [
                ("수상", water_total),
                ("유상", oil_total),
                ("유화제", emulsifier_total),
                ("기타", other_total)
            ]
            self.update_visualization(data, form_type=form_data["type"])
            
            # HLB 적합성에 따른 메시지 박스 표시
            if not is_hlb_in_range:
                QMessageBox.warning(self, "HLB 경고", 
                                f"유상+유화제 평균 HLB({avg_hlb_oil_emul:.2f})가 제형 권장 범위({form_data['hlb_range'][0]}~{form_data['hlb_range'][1]})를 벗어났습니다.")
            else:
                # 나머지 비율도 적합한지 확인
                ratio_issues = []
                if abs(diff_water) > 5:
                    ratio_issues.append(f"수상 비율 차이: {abs(diff_water):.1f}%")
                if abs(diff_oil) > 5:
                    ratio_issues.append(f"유상 비율 차이: {abs(diff_oil):.1f}%")
                if abs(diff_emulsifier) > 2:
                    ratio_issues.append(f"유화제 비율 차이: {abs(diff_emulsifier):.1f}%")
                    
                if ratio_issues:
                    QMessageBox.information(self, "비율 조정 필요", 
                                        "HLB는 적합하나 다음 비율 조정이 필요합니다:\n" + "\n".join(ratio_issues))
                else:
                    QMessageBox.information(self, "제형 적합", 
                                        f"유상+유화제 평균 HLB({avg_hlb_oil_emul:.2f})가 권장 범위 내이며, 성분 비율도 적절합니다.")
            
            self.save_state()
        except Exception as e:
            self.result_text.setText(f"계산 중 오류가 발생했습니다: {str(e)}")
            print(f"calculate_hlb 오류: {str(e)}")

    def suggest_emulsifiers(self):
        form = self.form_type.currentText()
        target_hlb = sum(FORMULATION_TYPES[form]["hlb_range"]) / 2
        total_emulsifier_pct = FORMULATION_TYPES[form]["emulsifier_ratio"] * 100

        # STEP 1: 소문자 기반 비교용 리스트
        df_ingredients_lower = self.df["INGREDIENT"].dropna().str.strip().str.lower().tolist()
        hlb_df = self.hlb_df.copy()
        hlb_df["INGREDIENT_LOWER"] = hlb_df["INGREDIENT"].str.strip().str.lower()

        # STEP 2: 유화제 후보 필터링 (키워드 기반 + 유화제 타입)
        keyword_mask = hlb_df["INGREDIENT_LOWER"].str.contains("emulsifier|유화제|계면활성제", case=False, na=False)
        emulsifiers_keyword = hlb_df[keyword_mask].dropna(subset=["HLB"])

        # STEP 3: 테이블에서 유화제로 분류된 성분도 수집
        emulsifier_names_in_table = set()
        for row in range(self.table.rowCount()):
            type_item = self.table.item(row, 2)
            name_item = self.table.item(row, 1)
            if type_item and name_item:
                if type_item.text().strip() == "유화제":
                    emulsifier_names_in_table.add(name_item.text().strip().lower())

        emulsifiers_from_table = hlb_df[hlb_df["INGREDIENT_LOWER"].isin(emulsifier_names_in_table)]

        # STEP 4: data_ing에 있는 유화제 우선 필터
        emulsifiers_data_ing = hlb_df[hlb_df["INGREDIENT_LOWER"].isin(df_ingredients_lower)]

        # STEP 5: 유화제가 충분하지 않으면 키워드 유화제 사용
        if len(emulsifiers_data_ing) >= 4:
            emulsifiers_final = emulsifiers_data_ing
        else:
            emulsifiers_final = pd.concat([emulsifiers_keyword, emulsifiers_from_table]).drop_duplicates(subset=["INGREDIENT_LOWER"])
            emulsifiers_final = emulsifiers_final.dropna(subset=["HLB"])

        if emulsifiers_final.empty:
            QMessageBox.information(self, "추천", "적합한 유화제 후보가 없습니다.")
            return

        # STEP 6: 유화제 조합 추천
        suggestions = []
        for i, row1 in emulsifiers_final.iterrows():
            for j, row2 in emulsifiers_final.iterrows():
                if i >= j:
                    continue
                hlb1, hlb2 = row1["HLB"], row2["HLB"]
                for ratio in np.arange(0.1, 0.91, 0.1):
                    combined_hlb = hlb1 * ratio + hlb2 * (1 - ratio)
                    if abs(combined_hlb - target_hlb) < 0.5:
                        suggestions.append({
                            "emulsifier1": row1["INGREDIENT"],
                            "emulsifier2": row2["INGREDIENT"],
                            "hlb1": hlb1,
                            "hlb2": hlb2,
                            "ratio": round(ratio, 2),
                            "combined_hlb": round(combined_hlb, 2)
                        })
                        if len(suggestions) >= 5:
                            break
                if len(suggestions) >= 5:
                    break
            if len(suggestions) >= 5:
                break

        if not suggestions:
            QMessageBox.information(self, "추천", "적합한 유화제 조합을 찾을 수 없습니다.")
            return

        # STEP 7: 결과 출력
        suggestion_text = "유화제 조합 추천:\n"

        def get_source(name):
            name_lower = name.strip().lower()
            in_data_ing = name_lower in df_ingredients_lower
            if in_data_ing:
                return "data_ing에서 확인됨"
            return "hlb값에서 가져온 성분"

        for s in suggestions:
            e1, e2 = s["emulsifier1"], s["emulsifier2"]
            r1, r2 = s["ratio"], 1 - s["ratio"]
            p1 = round(total_emulsifier_pct * r1, 2)
            p2 = round(total_emulsifier_pct * r2, 2)
            src1 = get_source(e1)
            src2 = get_source(e2)

            suggestion_text += (
                f"- {e1} (HLB {s['hlb1']}) + {e2} (HLB {s['hlb2']})\n"
                f"  → 비율: {int(r1 * 100)}% / {int(r2 * 100)}% → 조합 HLB: {s['combined_hlb']}\n"
                f"  → 출처:\n"
                f"    - {e1}: {src1}\n"
                f"    - {e2}: {src2}\n"
                f"  → 총 유화제 {total_emulsifier_pct:.1f}% 기준 사용량:\n"
                f"    - {e1}: {p1:.2f}%\n"
                f"    - {e2}: {p2:.2f}%\n\n"
            )

        self.result_text.setText(suggestion_text)
        self.save_state()



    def add_ingredient(self):
        name, ok = QInputDialog.getText(self, "성분 추가", "성분명:")
        if not ok or not name:
            return
        hlb, ok = QInputDialog.getDouble(self, "성분 추가", "HLB 값:", 0, 0, 20, 2)
        if not ok:
            return
        
        new_row = pd.DataFrame({"INGREDIENT": [name], "HLB": [hlb]})
        self.hlb_df = pd.concat([self.hlb_df, new_row], ignore_index=True)
        new_ing = pd.DataFrame({"INGREDIENT": [name], "코드": [f"NEW_{len(self.df)}"]})
        self.df = pd.concat([self.df, new_ing], ignore_index=True)
        self.setup_autocomplete()
        QMessageBox.information(self, "완료", f"{name} (HLB: {hlb}) 성분이 추가되었습니다.")

    def save_formulation(self):
        data = {
            "form_type": self.form_type.currentText(),
            "ingredients": [
                {
                    "code": self.table.item(r, 0).text() if self.table.item(r, 0) else "",
                    "name": self.table.item(r, 1).text() if self.table.item(r, 1) else "",
                    "type": self.table.item(r, 2).text() if self.table.item(r, 2) else "",
                    "percent": self.table.item(r, 3).text() if self.table.item(r, 3) else "",
                    "hlb": self.table.item(r, 4).text() if self.table.item(r, 4) else ""
                }
                for r in range(self.table.rowCount())
            ]
        }
        with open("제형.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "완료", "제형이 제형.json 파일로 저장되었습니다.")

    def load_formulation(self):
        try:
            with open("제형.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.form_type.setCurrentText(data["form_type"])
            self.table.setRowCount(len(data["ingredients"]))
            for r, ing in enumerate(data["ingredients"]):
                for c, key in enumerate(["code", "name", "type", "percent", "hlb"]):
                    self.table.setItem(r, c, QTableWidgetItem(ing[key]))
            self.setup_autocomplete()
            self.calculate_hlb()
            self.save_state()
            QMessageBox.information(self, "완료", "제형을 성공적으로 불러왔습니다.")
        except FileNotFoundError:
            QMessageBox.critical(self, "오류", "제형.json 파일을 찾을 수 없습니다.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 9))
    win = HLBDesigner()
    win.show()
    sys.exit(app.exec_())
