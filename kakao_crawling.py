import os, re, time, random, csv, datetime
from urllib.parse import urlparse
import requests
import pandas as pd
from slugify import slugify

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException


START_URLS = [
    "https://gift.kakao.com/page/26921?banner_id=1246&campaign_code=null"  
]
MAX_LIST_PAGES = 1         
MAX_PRODUCTS_PER_LIST = 3  

OUT_DIR = "dataset"
IMG_DIR = os.path.join(OUT_DIR, "images")
CSV_PATH = os.path.join(OUT_DIR, "products.csv")

REQUEST_TIMEOUT = 20
MIN_DELAY, MAX_DELAY = 1.2, 2.8 

def safe_mkdir(p):
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)

def rand_sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

def handle_alert(driver):
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        print(f"[INFO] 알림창 감지: {alert_text}")
        
        # 로그인 관련 알림창은 취소
        if "로그인" in alert_text:
            print("[INFO] 로그인 알림창 취소")
            alert.dismiss()
        else:
            print("[INFO] 알림창 확인")
            alert.accept()
        return True
    except NoAlertPresentException:
        return False
    except Exception as e:
        print(f"[WARNING] 알림창 처리 중 오류: {e}")
        return False

def now_kst_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")

def parse_price_to_int(text):
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None

def guess_product_id_from_url(url):
    m = re.search(r"/product/(\d+)", url)
    return m.group(1) if m else slugify(url)[:32]

def download_image(url, save_path):
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent":"Mozilla/5.0"})
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)

def build_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1440,900")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def extract_product_links_from_list(driver):
    # 알림창 처리
    handle_alert(driver)
    
    # 여러 선택자 시도
    selectors = [
        "a.link_thumb",
        "a[href*='/product/']",
        ".product_item a",
        ".item_thumb a",
        ".thumb_area a",
        "[class*='thumb'] a",
        ".product_link",
        "a[class*='product']"
    ]
    
    links = []
    
    for selector in selectors:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"[DEBUG] {selector}: {len(cards)}개 요소 발견")
            
            for a in cards:
                href = a.get_attribute("href")
                if href and "/product/" in href:
                    links.append(href)
                    
            if links:  # 링크를 찾았으면 더 이상 시도하지 않음
                break
                
        except UnexpectedAlertPresentException:
            handle_alert(driver)
            continue
        except Exception as e:
            print(f"[DEBUG] {selector} 시도 중 오류: {e}")
            continue
    
    # 중복 제거
    uniq = []
    for u in links:
        if u not in uniq:
            uniq.append(u)
    
    print(f"[INFO] 찾은 상품 링크 수: {len(uniq)}")
    if len(uniq) == 0:
        print("[WARNING] 상품 링크를 못 찾았습니다. 페이지 구조를 확인하세요.")
        # 디버깅을 위해 현재 페이지의 모든 링크 출력
        all_links = driver.find_elements(By.CSS_SELECTOR, "a")
        print(f"[DEBUG] 페이지 내 전체 링크 수: {len(all_links)}")
        product_links = [a.get_attribute("href") for a in all_links if a.get_attribute("href") and "/product/" in a.get_attribute("href")]
        print(f"[DEBUG] /product/ 포함 링크 수: {len(product_links)}")
    
    return uniq

def parse_product_detail(driver, url, category_hint=None, theme_hint=None):
    driver.get(url)
    rand_sleep()
    
    # 알림창 처리
    handle_alert(driver)
    
    # 상품 이름
    name = ""
    try:
        title_el = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h2.tit_subject"))
        )
        name = title_el.text.strip()
    except Exception as e:
        print(f"[ERROR] 상품 이름을 찾을 수 없습니다: {e}")
        name = "제목 없음"

    # 가격
    price_text = ""
    try:
        price_el = driver.find_element(By.CSS_SELECTOR, "span.txt_total")
        price_text = price_el.text.strip()
    except:
        pass
    
    price = parse_price_to_int(price_text) if price_text else None
    
    if not price:
        print(f"[WARNING] 가격을 찾을 수 없습니다: {url}")

    # 모든 이미지 수집
    all_images = []
    
    # 1. 대표 이미지 (메타 태그 우선)
    main_image_url = ""
    metas = driver.find_elements(By.CSS_SELECTOR, "meta[property='og:image']")
    if metas:
        main_image_url = metas[0].get_attribute("content")
    
    # 2. 상품 상세 이미지들 (상품설명 영역)
    detail_images = []
    
    # 상품설명 영역의 이미지들 찾기 (Shadow DOM 접근)
    try:
        # Shadow DOM에 접근해서 이미지 찾기
        shadow_host = driver.find_element(By.CSS_SELECTOR, "app-view-encapsuled-product-desc")
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", shadow_host)
        
        if shadow_root:
            # Shadow DOM 내부에서 스크롤해서 모든 이미지 로드 유도
            print("[DEBUG] 지연 로딩 이미지들을 로드하기 위해 스크롤 중...")
            
            # 여러 번 스크롤해서 모든 이미지 로드 유도
            for i in range(3):
                driver.execute_script("""
                    var shadowRoot = arguments[0];
                    var editorContents = shadowRoot.querySelector('div._editor_contents');
                    if (editorContents) {
                        // 천천히 스크롤 다운
                        var height = editorContents.scrollHeight;
                        for (var j = 0; j < height; j += 100) {
                            editorContents.scrollTop = j;
                        }
                        editorContents.scrollTop = height;
                    }
                """, shadow_root)
                time.sleep(2)
                
                # 다시 위로
                driver.execute_script("""
                    var shadowRoot = arguments[0];
                    var editorContents = shadowRoot.querySelector('div._editor_contents');
                    if (editorContents) {
                        editorContents.scrollTop = 0;
                    }
                """, shadow_root)
                time.sleep(1)
            
            # 최종 대기
            print("[DEBUG] 이미지 로딩 완료 대기 중...")
            time.sleep(5)
            
            # Shadow DOM 내부의 _editor_contents에서 이미지 찾기
            imgs = driver.execute_script("""
                var shadowRoot = arguments[0];
                var editorContents = shadowRoot.querySelector('div._editor_contents');
                if (editorContents) {
                    var allImgs = editorContents.querySelectorAll('img');
                    var validImgs = [];
                    
                    for (var i = 0; i < allImgs.length; i++) {
                        var img = allImgs[i];
                        var src = img.src || img.getAttribute('data-original-src') || img.getAttribute('data-src');
                        
                        // 유효한 이미지 URL이 있는지 확인
                        if (src && (src.startsWith('http://') || src.startsWith('https://'))) {
                            // 빈 이미지나 플레이스홀더 제외
                            if (!src.includes('1x1') && !src.includes('pixel') && !src.includes('transparent') && !src.includes('blank')) {
                                validImgs.push(img);
                            }
                        }
                    }
                    
                    return validImgs;
                }
                return [];
            """, shadow_root)
            
            print(f"[DEBUG] Shadow DOM에서 총 {len(imgs)}개 유효한 img 요소 발견")
            
            for i, img in enumerate(imgs):
                # 여러 속성에서 이미지 URL 시도 (data-original-src 우선)
                src = (img.get_attribute("data-original-src") or 
                      img.get_attribute("data-src") or
                      img.get_attribute("src"))
                
                print(f"[DEBUG] 이미지 {i+1}: {src}")
                
                if src and ("http://" in src or "https://" in src):
                    # 1px.png 같은 플레이스홀더 제외
                    if not any(x in src.lower() for x in [
                        "icon", "logo", "thumb_small", "btn_", "arrow",
                        "1x1", "1px", "pixel", "transparent", "blank", "placeholder"
                    ]):
                        detail_images.append(src)
                        print(f"[DEBUG] 유효한 이미지 추가: {src}")
                    else:
                        print(f"[DEBUG] 필터링으로 제외: {src}")
                        
            print(f"[INFO] Shadow DOM _editor_contents에서 {len(detail_images)}개 유효한 이미지 발견")
        else:
            print("[WARNING] Shadow Root를 찾을 수 없음")
            
    except Exception as e:
        print(f"[WARNING] Shadow DOM 접근 실패: {e}")
        # 백업 선택자들 (일반 DOM)
        fallback_selectors = [
            "div._editor_contents img",
            "[imglazyload] img",
            "div[class*='editor'] img", 
            ".wrap_editor img"
        ]
        
        for selector in fallback_selectors:
            try:
                imgs = driver.find_elements(By.CSS_SELECTOR, selector)
                for img in imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-original-src")
                    if src and ("http://" in src or "https://" in src):
                        if not any(x in src.lower() for x in ["icon", "logo", "thumb_small", "btn_", "arrow"]):
                            detail_images.append(src)
                print(f"[INFO] {selector}에서 {len(imgs)}개 이미지 요소 발견")
                if detail_images:
                    break
            except Exception as ex:
                print(f"[DEBUG] {selector} 시도 실패: {ex}")
                continue
    
    # 중복 제거
    detail_images = list(dict.fromkeys(detail_images))
    
    # 대표 이미지가 없으면 첫 번째 상세 이미지를 대표로 사용
    if not main_image_url and detail_images:
        main_image_url = detail_images[0]
    
    # 전체 이미지 리스트 구성
    if main_image_url:
        all_images.append(("main", main_image_url))
    
    # 상세 이미지들 추가 (대표 이미지와 중복되지 않도록)
    detail_count = 1
    for img_url in detail_images:
        if img_url != main_image_url:  # 대표 이미지와 다른 경우만
            all_images.append((f"detail{detail_count}", img_url))
            detail_count += 1


    # 카테고리/테마(노출되는 경우만)
    category = category_hint or ""
    theme = theme_hint or ""
    # 예: 빵부스러기(브레드크럼) 탐색
    for bc_sel in [".breadcrumb", "nav.breadcrumb", "ul.breadcrumb"]:
        bc = driver.find_elements(By.CSS_SELECTOR, bc_sel + " li, " + bc_sel + " a")
        if bc:
            crumbs = [el.text.strip() for el in bc if el.text.strip()]
            if len(crumbs) >= 2:
                category = category or crumbs[1]  # 대략 상위 카테고리로 추정
            break

    # 이미지 저장
    product_id = guess_product_id_from_url(url)
    image_rel_paths = []
    main_image_path = ""
    
    if all_images:
        # 상품별 폴더 생성
        product_img_dir = os.path.join(IMG_DIR, product_id)
        safe_mkdir(product_img_dir)
        
        print(f"[INFO] {len(all_images)}개 이미지 다운로드 시작: {product_id}")
        
        for img_name, img_url in all_images:
            try:
                ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
                filename = f"{img_name}{ext}"
                save_path = os.path.join(product_img_dir, filename)
                rel_path = f"images/{product_id}/{filename}"
                
                download_image(img_url, save_path)
                image_rel_paths.append(rel_path)
                
                # 대표 이미지 경로 저장 (CSV용)
                if img_name == "main":
                    main_image_path = rel_path
                
                print(f"[INFO] 이미지 저장: {filename}")
            except Exception as e:
                print(f"[WARNING] 이미지 다운로드 실패 ({img_name}): {e}")
                continue
        
        print(f"[INFO] 이미지 저장 완료: {product_id} ({len(image_rel_paths)}개)")
    
    # CSV에는 대표 이미지 경로만 저장 (기존 호환성 유지)
    image_rel_path = main_image_path
    
    # features에 상품설명 이미지 경로들 저장
    detail_image_paths = []
    for rel_path in image_rel_paths:
        if "/detail" in rel_path:  # detail1, detail2 등이 포함된 경로만
            detail_image_paths.append(rel_path)
    features_str = "; ".join(detail_image_paths) if detail_image_paths else ""

    row = {
        "product_id": product_id,
        "name": name,
        "price": price,
        "image_path": image_rel_path,
        "features": features_str,
        "category": category,
        "theme": theme,
        "source_url": url,
        "crawled_at": datetime.datetime.now().isoformat(timespec="seconds")
    }
    return row

def scroll_to_load_more(driver, max_scrolls=5):
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        
        last_height = new_height
        scroll_count += 1
        print(f"[INFO] 스크롤 {scroll_count}회 완료")

def crawl():
    safe_mkdir(OUT_DIR)
    safe_mkdir(IMG_DIR)

    driver = build_driver()
    all_rows = []
    failures = []

    try:
        for start_url in START_URLS:
            print(f"\n[INFO] 크롤링 시작: {start_url}")
            driver.get(start_url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            rand_sleep()
            
            # 알림창 처리
            handle_alert(driver)
            
            for page_idx in range(1, MAX_LIST_PAGES + 1):
                print(f"\n[INFO] === 페이지 {page_idx} 처리 중 ===")
                product_links = extract_product_links_from_list(driver)[:MAX_PRODUCTS_PER_LIST]
                
                if not product_links:
                    print("[WARNING] 상품 링크를 찾을 수 없습니다. CSS 선택자를 확인하세요.")
                    break

                print(f"[INFO] 처리할 상품 수: {len(product_links)}")
                for idx, link in enumerate(product_links, 1):
                    try:
                        print(f"\n[{idx}/{len(product_links)}] 크롤링 중: {link}")
                        rand_sleep()
                        row = parse_product_detail(driver, link)
                        all_rows.append(row)
                        print(f"[OK] {row['name']} - {row['price']}원")
                    except Exception as e:
                        print(f"[FAIL] {link}")
                        print(f"[ERROR] {str(e)}")
                        failures.append(link)
                        continue

                next_btn = None
                for sel in ["a.next", "button.next", "a[rel='next']", "[class*='next']", "[class*='Next']"]:
                    btns = driver.find_elements(By.CSS_SELECTOR, sel)
                    if btns and btns[0].is_displayed():
                        next_btn = btns[0]
                        break
                
                if next_btn:
                    print("[INFO] 다음 페이지로 이동 중...")
                    driver.execute_script("arguments[0].click();", next_btn)
                    rand_sleep()
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                    )
                else:
                    print("[INFO] 더 이상 페이지가 없습니다.")
                    break 
    finally:
        driver.quit()
        print("\n[INFO] 브라우저 종료")

    df = pd.DataFrame(all_rows)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} rows to {CSV_PATH}")

    if failures:
        with open(os.path.join(OUT_DIR, "failures.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(failures))
        print(f"Failures logged: {len(failures)}")

if __name__ == "__main__":
    crawl()
