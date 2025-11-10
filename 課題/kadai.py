import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser # robots.txt 読み込み
import re
import time
from collections import deque # 幅優先探索(BFS)用キュー

# クロール対象外とするファイル拡張子
EXCLUDED_EXTENSIONS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', 
    '.bmp', '.webp', '.tiff', '.css', '.js', '.xml', '.zip',
    '.mp4', '.mov', '.avi', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
)

# User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def crawl_same_domain(start_url, max_pages=500):
    """
    同一ドメイン内のHTMLページをクロールし、URLとページタイトルを収集する。
    robots.txt を尊重し、BFS(幅優先探索)で実行する。

    :param start_url: クロールを開始するURL
    :param max_pages: 収集する最大ページ数
    :return: {URL: <title>} の辞書
    """
    
    # --- 1. 初期設定 ---
    parsed_uri = urlparse(start_url)
    base_domain = parsed_uri.netloc
    base_scheme = parsed_uri.scheme
    
    normalized_start_url = start_url.rstrip('/')
    
    # BFS用のキュー
    urls_to_visit = deque([normalized_start_url]) 
    
    # 訪問済み・キュー投入済みURLのセット
    seen_urls = {normalized_start_url} 
    
    scraped_pages = {} # 結果辞書

    # セッション設定
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})

    # --- 1.5. robots.txt の設定 ---
    robots_url = f"{base_scheme}://{base_domain}/robots.txt"
    robot_parser = RobotFileParser()
    robot_parser.set_url(robots_url)
    try:
        robot_parser.read()
        print(f"robots.txt を読み込みました: {robots_url}")
    except Exception as e:
        print(f"警告: robots.txt の読み込みに失敗: {e}")

    print(f"--- クロール開始 ---")
    print(f"対象ドメイン: {base_domain}")
    print(f"最大ページ数: {max_pages}")

    # --- 2. クロールループ ---
    while urls_to_visit and len(scraped_pages) < max_pages:
        current_url = urls_to_visit.popleft() # キューの先頭からURLを取得
        
        # ファイル拡張子で除外
        if any(current_url.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            continue
            
        # robots.txt のルールを確認
        if not robot_parser.can_fetch(USER_AGENT, current_url):
            print(f"  robots.txtによりスキップ: {current_url}")
            continue
            
        print(f"  処理中 [{len(scraped_pages) + 1}/{max_pages}]: {current_url}")
        
        try:
            # ページ取得
            response = session.get(current_url, timeout=10)
            
            # ステータスコードチェック
            if response.status_code != 200:
                print(f"    スキップ (Status): {response.status_code}")
                continue
            
            # Content-Typeチェック (HTMLのみ対象)
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                print(f"    スキップ (Content-Type): {content_type}")
                continue

            # --- 3. HTML解析とタイトル抽出 ---
            
            # ★★★ 文字化け対策 ★★★
            # apparent_encoding (コンテンツから推測したエンコーディング) を
            # response.encoding に設定してから .text にアクセスする
            response.encoding = response.apparent_encoding
            html_content = response.text
            
            # HTMLコメントを削除
            html_content_cleaned = re.sub(r'', '', html_content, flags=re.DOTALL)
            
            soup = BeautifulSoup(html_content_cleaned, 'html.parser')
            
            title_tag = soup.find('title')
            # タイトルが取得できない場合は「タイトルなし」とする
            title_text = title_tag.string.strip() if title_tag and title_tag.string else "タイトルなし"
            
            scraped_pages[current_url] = title_text

            # --- 4. リンクの抽出と追加 ---
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                # 不要なリンク（電話番号、メール、JS）を除外
                if href.startswith(('tel:', 'mailto:', 'javascript:')):
                    continue
                
                # 絶対URLへの変換とフラグメント(#)の除去
                full_url = urljoin(current_url, href).split('#')[0]
                parsed_full_url = urlparse(full_url)
                
                # 同一ドメインかチェック
                is_same_domain = parsed_full_url.scheme in ['http', 'https'] and parsed_full_url.netloc == base_domain
                
                if is_same_domain:
                    normalized_url = full_url.rstrip('/') # URL正規化
                    
                    if normalized_url not in seen_urls:
                        seen_urls.add(normalized_url) # 訪問リストに追加
                        urls_to_visit.append(normalized_url) # キューに追加
            
        except requests.exceptions.RequestException as e:
            print(f"    エラー (Request): {e}")
        except Exception as e:
            print(f"    エラー (Other): {e}")
        
        # 負荷軽減のための待機
        time.sleep(0.5) 

    print("\n--- クロール完了 ---")
    return scraped_pages

# --- 実行 ---
if __name__ == "__main__":
    start_url = "https://www.musashino-u.ac.jp/"
    # 上限20ページで実行
    result_dict = crawl_same_domain(start_url, max_pages=20) 
    
    print("\n=== 収集結果 ===")
    # 結果の表示
    for url, title in result_dict.items():
        print(f"URL: {url}\nTITLE: {title}\n---")
        
    print(f"\n総ページ数: {len(result_dict)}")