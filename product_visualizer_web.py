import streamlit as st
import pandas as pd
from PIL import Image
import os
from pathlib import Path
import math

# 페이지 설정
st.set_page_config(
    page_title="상품 데이터 시각화",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_image_safe(image_path, base_dir, max_width=300, max_height=400):
    try:
        full_path = os.path.join(base_dir, image_path)
        if os.path.exists(full_path):
            image = Image.open(full_path)
            image = image.convert('RGB')
            
            original_width, original_height = image.size
            
            width_ratio = max_width / original_width
            height_ratio = max_height / original_height
            
            ratio = min(width_ratio, height_ratio)
            
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            return image
        else:
            placeholder = Image.new('RGB', (max_width, max_height), color='lightgray')
            return placeholder
    except Exception as e:
        st.error(f"이미지 로드 실패: {e}")
        placeholder = Image.new('RGB', (max_width, max_height), color='lightgray')
        return placeholder

def main():
    st.title("상품 데이터 시각화 도구")
    st.markdown("---")
    
    with st.sidebar:
        st.header("📁 파일 설정")
        
        # CSV 파일 업로드
        uploaded_file = st.file_uploader(
            "CSV 파일을 업로드하세요",
            type=['csv'],
            help="상품 데이터가 포함된 CSV 파일을 선택하세요"
        )
        
        # 또는 기본 파일 사용
        st.markdown("**또는**")
        use_default = st.checkbox("기본 파일 사용 (dataset/products.csv)")
        
        if use_default:
            default_path = "dataset/products.csv"
            if os.path.exists(default_path):
                uploaded_file = default_path
                st.success("기본 파일을 사용합니다!")
            else:
                st.error("기본 파일을 찾을 수 없습니다.")
                uploaded_file = None
    
    # 기본 파일 자동 로드
    if uploaded_file is None and not use_default:
        default_path = "dataset/products.csv"
        if os.path.exists(default_path):
            uploaded_file = default_path
            st.info("기본 파일(dataset/products.csv)을 자동으로 로드했습니다!")
    
    if uploaded_file is not None:
        try:
            if isinstance(uploaded_file, str):
                df = pd.read_csv(uploaded_file)
                base_dir = os.path.dirname(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
                base_dir = "."
            
            st.success(f"총 {len(df)}개의 상품 데이터를 로드했습니다!")
            
            with st.sidebar:
                st.header("필터링 옵션")
                
                search_term = st.text_input("상품명 검색", placeholder="검색어를 입력하세요")
                
                if 'price' in df.columns and df['price'].notna().any():
                    min_price = int(df['price'].min())
                    max_price = int(df['price'].max())
                    price_range = st.slider(
                        "가격 범위",
                        min_value=min_price,
                        max_value=max_price,
                        value=(min_price, max_price),
                        format="%d원"
                    )
                else:
                    price_range = None
                
                if 'category' in df.columns:
                    categories = df['category'].dropna().unique()
                    if len(categories) > 0:
                        selected_categories = st.multiselect(
                            "카테고리 선택",
                            options=categories,
                            default=categories
                        )
                    else:
                        selected_categories = []
                else:
                    selected_categories = []
                
                items_per_page = st.selectbox(
                    "페이지당 상품 수",
                    options=[6, 9, 12, 15, 18],
                    index=2
                )
            
            filtered_df = df.copy()
            
            if search_term:
                mask = filtered_df['name'].str.contains(search_term, case=False, na=False)
                filtered_df = filtered_df[mask]
            
            if price_range and 'price' in filtered_df.columns:
                mask = (filtered_df['price'] >= price_range[0]) & (filtered_df['price'] <= price_range[1])
                filtered_df = filtered_df[mask]
            
            if selected_categories and 'category' in filtered_df.columns:
                mask = filtered_df['category'].isin(selected_categories)
                filtered_df = filtered_df[mask]
            
            if len(filtered_df) == 0:
                st.warning("⚠️ 필터 조건에 맞는 상품이 없습니다.")
                return
            
            st.info(f"필터링 결과: {len(filtered_df)}개 상품")
            
            total_pages = math.ceil(len(filtered_df) / items_per_page)
            
            if total_pages > 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    page = st.selectbox(
                        f"페이지 선택 (총 {total_pages}페이지)",
                        options=range(1, total_pages + 1),
                        format_func=lambda x: f"{x} / {total_pages}"
                    )
            else:
                page = 1
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_data = filtered_df.iloc[start_idx:end_idx]
            
            cols_per_row = 3
            rows = math.ceil(len(page_data) / cols_per_row)
            
            for row in range(rows):
                cols = st.columns(cols_per_row)
                
                for col_idx in range(cols_per_row):
                    item_idx = row * cols_per_row + col_idx
                    
                    if item_idx < len(page_data):
                        item = page_data.iloc[item_idx]
                        
                        with cols[col_idx]:
                            with st.container():
                                st.markdown(f"### 🏷️ ID: {item['product_id']}")
                                
                                if 'image_path' in item and pd.notna(item['image_path']):
                                    image = load_image_safe(item['image_path'], base_dir, max_width=300, max_height=300)
                                    st.image(image, width=300)
                                else:
                                    st.info("이미지 없음")
                                
                                st.markdown(f"**상품명:** {item['name'][:100]}{'...' if len(str(item['name'])) > 100 else ''}")
                                
                                if 'price' in item and pd.notna(item['price']):
                                    st.markdown(f"**가격:** :red[{int(item['price']):,}원]")
                                
                                if 'category' in item and pd.notna(item['category']):
                                    st.markdown(f"**카테고리:** {item['category']}")
                                
                                if 'features' in item and pd.notna(item['features']):
                                    features = str(item['features'])
                                    detail_count = len([f for f in features.split(';') if f.strip()])
                                    st.markdown(f"**상세 이미지:** {detail_count}개")
                                
                                if st.button(f"상세보기", key=f"detail_{item['product_id']}"):
                                    show_detail_modal(item, base_dir)
                                
                                st.markdown("---")
            
            with st.expander("데이터 통계"):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("총 상품 수", len(filtered_df))
                
                with col2:
                    if 'price' in filtered_df.columns and filtered_df['price'].notna().any():
                        avg_price = filtered_df['price'].mean()
                        st.metric("평균 가격", f"{int(avg_price):,}원")
                    else:
                        st.metric("평균 가격", "N/A")
                
                with col3:
                    if 'category' in filtered_df.columns:
                        unique_categories = filtered_df['category'].nunique()
                        st.metric("카테고리 수", unique_categories)
                    else:
                        st.metric("카테고리 수", "N/A")
                
                with col4:
                    if 'features' in filtered_df.columns:
                        total_images = 0
                        for features in filtered_df['features'].dropna():
                            total_images += len([f for f in str(features).split(';') if f.strip()])
                        st.metric("총 상세 이미지", total_images)
                    else:
                        st.metric("총 상세 이미지", "N/A")
        
        except Exception as e:
            st.error(f"파일을 처리하는 중 오류가 발생했습니다: {str(e)}")
    
    else:
        st.info("사이드바에서 CSV 파일을 업로드하거나 기본 파일을 사용해주세요.")
        
        with st.expander("사용법 안내"):
            st.markdown("""
            ### 사용 방법
            
            1. **파일 업로드**: 사이드바에서 CSV 파일을 업로드하거나 기본 파일을 사용하세요
            2. **필터링**: 검색어, 가격 범위, 카테고리로 상품을 필터링할 수 있습니다
            3. **페이지네이션**: 많은 상품이 있을 때 페이지별로 나누어 볼 수 있습니다
            4. **상세보기**: 각 상품의 상세보기 버튼을 클릭하면 더 자세한 정보를 볼 수 있습니다
            
            ### CSV 파일 형식
            
            CSV 파일에는 다음 컬럼들이 포함되어야 합니다:
            - `product_id`: 상품 ID
            - `name`: 상품명
            - `price`: 가격 (선택사항)
            - `image_path`: 메인 이미지 경로
            - `features`: 상세 이미지 경로들 (세미콜론으로 구분)
            - `category`: 카테고리 (선택사항)
            """)

@st.dialog("상품 상세 정보")
def show_detail_modal(item, base_dir):
    st.markdown(f"### {item['product_id']}")
    st.markdown(f"**상품명:** {item['name']}")
    
    if 'price' in item and pd.notna(item['price']):
        st.markdown(f"**가격:** :red[{int(item['price']):,}원]")
    
    if 'category' in item and pd.notna(item['category']):
        st.markdown(f"**카테고리:** {item['category']}")
    
    st.markdown("#### 메인 이미지")
    if 'image_path' in item and pd.notna(item['image_path']):
        image = load_image_safe(item['image_path'], base_dir, max_width=400, max_height=500)
        st.image(image, width=400)
    else:
        st.info("메인 이미지 없음")
    
    if 'features' in item and pd.notna(item['features']):
        features = str(item['features'])
        detail_images = [f.strip() for f in features.split(';') if f.strip()]
        
        if detail_images:
            st.markdown(f"#### 🖼️ 상세 이미지 ({len(detail_images)}개)")
            
            cols_per_row = 2
            rows = math.ceil(len(detail_images) / cols_per_row)
            
            for row in range(rows):
                cols = st.columns(cols_per_row)
                
                for col_idx in range(cols_per_row):
                    img_idx = row * cols_per_row + col_idx
                    
                    if img_idx < len(detail_images):
                        with cols[col_idx]:
                            img_path = detail_images[img_idx]
                            st.markdown(f"**{os.path.basename(img_path)}**")
                            image = load_image_safe(img_path, base_dir, max_width=250, max_height=300)
                            st.image(image, width=250)
    
    if 'source_url' in item and pd.notna(item['source_url']):
        st.markdown(f"**원본 URL:** [링크 열기]({item['source_url']})")

if __name__ == "__main__":
    main()
