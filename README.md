# Present-Data-Generation

### 폴더 구조
```
📁 Present-Data-Generation/
├── dataset/
│   ├── images/                  # 크롤링 이미지 저장 위치 (각 product_id로 폴더 생성, 안에 main 이미지와 detail 이미지 존재)
│   └── products.csv             # 최종 데이터셋
├── kakao_crawling.py            # 카카오톡 선물하기 크롤링 코드 (해당 URL 페이지에서 상위 n개, n'개의 페이지 탐색)
├── kakao_crawling_category.py   # 카카오톡 선물하기 카테코리 항목별 n개 크롤링
├── product_visualizer_web.py    # 상품 데이터 streamlit 이용 웹 시각화
└── requirements.txt             # 파이썬 설치 패키지
```

### 데이터 시각화하여 확인
```bash
streamlit run product_visualizer_web.py
```