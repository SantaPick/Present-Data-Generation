import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import base64
from pathlib import Path
from PIL import Image
import tiktoken
import io

load_dotenv()

OUT_DIR = "dataset"
CSV_PATH = os.path.join(OUT_DIR, "products.csv")
OUTPUT_CSV_PATH = os.path.join(OUT_DIR, "products_with_description.csv")
PROMPT_PATH = "prompts/description_generate_prompt.txt"

MAX_INPUT_TOKENS = 128000
MAX_REQUEST_SIZE_MB = 10

START = 0
END = 200

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY가 없습니다.")

client = OpenAI(api_key=api_key)

def load_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()

def calculate_image_tokens(width, height):
    if width <= 512 and height <= 512:
        return 85
    else:
        w_tiles = (width + 511) // 512
        h_tiles = (height + 511) // 512
        return (w_tiles * h_tiles * 170) + 85

def encode_and_measure_image(image_path, max_size=1024):
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((max_size, max_size))
            final_w, final_h = img.size
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            size_bytes = buffer.getbuffer().nbytes
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            tokens = calculate_image_tokens(final_w, final_h)
            return base64_str, tokens, size_bytes
    except Exception as e:
        print(f"이미지 처리 실패: {image_path}, {e}")
        return None, 0, 0

def prepare_image_messages(image_paths, text_prompt):
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    text_tokens = len(encoding.encode(text_prompt))
    target_images = image_paths
    image_messages = []
    total_image_tokens = 0
    total_image_size_mb = 0.0
    for img_path in target_images:
        full_path = os.path.join(OUT_DIR, img_path.strip())
        if not os.path.exists(full_path):
            continue
        base64_image, tokens, size_bytes = encode_and_measure_image(full_path)
        if base64_image:
            size_mb = size_bytes / (1024 * 1024)
            if total_image_size_mb + size_mb > MAX_REQUEST_SIZE_MB:
                print(f"용량 제한 초과로 이미지 제외: {img_path}")
                break
            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            total_image_tokens += tokens
            total_image_size_mb += size_mb
    total_tokens = text_tokens + total_image_tokens
    print(f"[사용량 예측]")
    print(f"   - 이미지 수: {len(image_messages)}장 (리사이징 됨)")
    print(f"   - 텍스트 토큰: {text_tokens:,}")
    print(f"   - 이미지 토큰: {total_image_tokens:,}")
    print(f"   - 총 합계 토큰: {total_tokens:,}")
    print(f"   - 요청 데이터 크기: {total_image_size_mb:.2f} MB")
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
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f" GPT 오류 발생: {e}")
        if hasattr(e, 'response') and e.response:
             print(f"상세 정보: {e.response.json()}")
        return ""

def main():
    print("상품 설명 생성 시작...")
    prompt_template = load_prompt()
    if not os.path.exists(CSV_PATH):
        print(f"오류: {CSV_PATH} 파일이 없습니다.")
        return
    if os.path.exists(OUTPUT_CSV_PATH):
        print(f"기존 작업 파일 발견: {OUTPUT_CSV_PATH}")
        df_output = pd.read_csv(OUTPUT_CSV_PATH)
    else:
        print(f"새 작업 파일 생성 시작")
        df_output = pd.read_csv(CSV_PATH)
        df_output["description"] = ""
    start = START
    end = END if END is not None else len(df_output)
    df_to_process = df_output.iloc[start:end]
    for idx, row in df_to_process.iterrows():
        print(f"\n[{idx}] 처리 중: {row['name'][:30]}...")
        description = generate_description(row["name"], row["category"], row["features"], prompt_template)
        df_output.at[idx, "description"] = description
        if description:
            print(f"--> 성공! (결과 길이: {len(description)}자)")
        else:
            print("--> 실패")
        if (idx + 1) % 10 == 0:
            df_output.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    df_output.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {OUTPUT_CSV_PATH}")

if __name__ == "__main__":
    main()