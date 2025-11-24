# Present-Data-Generation

## 폴더 구조
```
📁 Present-Data-Generation/
├── dataset/
│   ├── images/                  # 크롤링 이미지 저장 위치 (각 product_id로 폴더 생성, 안에 main 이미지와 detail 이미지 존재)
│   └── products.csv             # 최종 데이터셋
├── kakao_crawling.py            # 카카오톡 선물하기 크롤링 코드 (해당 URL 페이지에서 상위 n개, n'개의 페이지 탐색)
├── kakao_crawling_category.py   # 카카오톡 선물하기 카테코리 항목별 n개 크롤링
├── product_visualizer_web.py    # 상품 데이터 streamlit 이용 웹 시각화
├── generate_description.py      # products.csv 파일에 description 피처를 추가한 csv 파일 생성 (gpt api 이용 생성성)
└── requirements.txt             # 파이썬 설치 패키지
```

## 데이터 시각화하여 확인
### 1. 초기 셋팅 (dataset)
- 루트 폴더에 dataset 압축해제하여 위치

### 2. streamlit을 통한 웹에서 시각화
```bash
streamlit run product_visualizer_web.py
# http://localhost:8501에 접속
```

## description 피처 생성
### 1. 환경 셋팅
```bash
# 가상환경 생성 (Linux/MacOS)
python3.11 -m venv env

# (Window)
py -3.11 -m venv env

# 의존성 설치
pip install -r requirements.txt
```

### 2. API 토큰 셋팅
.env 파일 루트에 생성:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 프롬프트 수정
- prompts/description_generate_prompt.txt 파일에 있는 프롬프트 수정
- 자유롭게 few-shot 같은것 추가
- 단, '상품명: {name}'과 '카테고리: {category}'는 건들지 말기