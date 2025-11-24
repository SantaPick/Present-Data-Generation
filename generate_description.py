import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import base64
from pathlib import Path
from PIL import Image
import tiktoken

load_dotenv()

OUT_DIR = "dataset"
CSV_PATH = os.path.join(OUT_DIR, "products.csv")
OUTPUT_CSV_PATH = os.path.join(OUT_DIR, "products_with_description.csv")
PROMPT_PATH = "prompts/description_generate_prompt.txt"

MAX_INPUT_TOKENS = 128000
MAX_REQUEST_SIZE_MB = 50

START = 0
END = 1     # START부터 END-1까지 처리할 상품 수

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

client = OpenAI(api_key=api_key)

def load_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()

def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"이미지 인코딩 실패: {image_path}, 오류: {e}")
        return None

def estimate_image_tokens(image_path):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            # OpenAI Vision API 토큰 계산 방식:
            # 512x512 이하: 85 토큰
            # 그 이상: (width * height) / (512 * 512) * 170 + 85 (오버헤드)
            if width <= 512 and height <= 512:
                return 85
            else:
                tiles = ((width + 511) // 512) * ((height + 511) // 512)
                return tiles * 170 + 85
    except Exception as e:
        print(f"이미지 토큰 추정 실패: {image_path}, 오류: {e}")
        return 1000

def prepare_image_messages(image_paths, text_prompt):
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    text_tokens = len(encoding.encode(text_prompt))
    available_tokens = MAX_INPUT_TOKENS - text_tokens - 500
    used_tokens = 0
    used_size_mb = 0
    image_messages = []
    
    for img_path in image_paths:
        full_path = os.path.join(OUT_DIR, img_path.strip())
        
        if not os.path.exists(full_path):
            continue
        
        ext = Path(full_path).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png"]:
            continue
        
        file_size_mb = os.path.getsize(full_path) / (1024 * 1024)
        estimated_tokens = estimate_image_tokens(full_path)
        estimated_base64_size_mb = file_size_mb * 1.33
        
        if used_tokens + estimated_tokens > available_tokens:
            print(f"토큰 제한 초과로 이미지 제외: {img_path} (예상 토큰: {estimated_tokens})")
            break
        
        if used_size_mb + estimated_base64_size_mb > MAX_REQUEST_SIZE_MB:
            print(f"요청 크기 제한 초과로 이미지 제외: {img_path} (예상 크기: {estimated_base64_size_mb:.2f}MB)")
            break
        
        base64_image = encode_image(full_path)
        if base64_image:
            mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            })
            used_tokens += estimated_tokens
            used_size_mb += estimated_base64_size_mb
    
    print(f"텍스트 토큰: {text_tokens}, 이미지 예상 토큰: {used_tokens}, 총 사용 토큰: {text_tokens + used_tokens}")
    print(f"예상 요청 크기: {used_size_mb:.2f}MB / {MAX_REQUEST_SIZE_MB}MB")
    return image_messages

def generate_description(name, category, image_paths, prompt_template):
    if pd.isna(image_paths) or image_paths == "":
        image_list = []
    else:
        image_list = [path.strip() for path in str(image_paths).split(";") if path.strip()]
    
    prompt = prompt_template.format(name=name, category=category)
    
    image_messages = prepare_image_messages(image_list, prompt)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                *image_messages
            ]
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500
        )
        
        description = response.choices[0].message.content.strip()
        return description
    except Exception as e:
        print(f"GPT API 호출 실패: {e}")
        import traceback
        error_detail = str(e)
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json()
            except:
                pass
        print(f"상세 오류: {error_detail}")
        return ""

def main():
    print("상품 설명 생성 시작...")
    
    prompt_template = load_prompt()
    print(f"프롬프트 로드 완료: {PROMPT_PATH}")
    
    df = pd.read_csv(CSV_PATH)
    print(f"총 {len(df)}개의 상품을 읽었습니다.")
    
    start = START
    end = END if END is not None else len(df)
    
    if start < 0 or start >= len(df):
        raise ValueError(f"START 값이 유효하지 않습니다. (0 이상 {len(df)-1} 이하여야 합니다)")
    if end is not None and (end < start or end > len(df)):
        raise ValueError(f"END 값이 유효하지 않습니다. (START 이상 {len(df)} 이하여야 합니다)")
    
    print(f"처리 범위: 인덱스 {start}부터 {end-1}까지 ({end-start}개 상품)")
    
    df_output = df.copy()
    
    if "description" not in df_output.columns:
        df_output["description"] = ""
    
    df_to_process = df.iloc[start:end]
    
    for i, (idx, row) in enumerate(df_to_process.iterrows()):
        current_num = i + 1
        total = len(df_to_process)
        print(f"\n[{current_num}/{total}] (전체 인덱스: {idx}) 처리 중: {row['name'][:50]}...")
        
        name = row["name"]
        category = row["category"]
        features = row["features"]
        
        description = generate_description(name, category, features, prompt_template)
        
        df_output.at[idx, "description"] = description
        
        if description:
            print(f"설명 생성 완료 (길이: {len(description)}자)")
        else:
            print(f"설명 생성 실패")
    
    df_output.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\n완료! 결과가 {OUTPUT_CSV_PATH}에 저장되었습니다.")

if __name__ == "__main__":
    main()
