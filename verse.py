import pandas as pd
from PIL import Image
import streamlit as st
import os

# データの保存先ファイルと画像保存フォルダ
DATA_FILE = "aipri_data.csv"
IMAGE_DIR = "aipri_images"

# フォルダがない場合は作成
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# データの読み込み関数
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["id", "code_name", "bullet", "character", "image_path"])

data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio("選択してください", ["コレクション一覧・検索", "プリフォトを追加する"])

# 弾数の選択肢リスト（必要に応じて追加・変更してください）
BULLET_OPTIONS = [
    "第1弾", "第2弾", "第3弾", "第4弾", "第5弾", "第6弾", 
    "シンクロフェス", "その他・プロモーション"
]

# ---------------------------------------------------------
# 1. コレクション一覧・検索画面
# ---------------------------------------------------------
if menu == "コレクション一覧・検索":
    st.header("📖 マイ・プリフォトコレクション")

    if data.empty:
        st.info("まだプリフォトが登録されていません。「プリフォトを追加する」から登録してみましょう！")
    else:
        # 絞り込みフィルター
        st.sidebar.subheader("🔍 絞り込み検索")
        existing_bullets = [b for b in BULLET_OPTIONS if b in data["bullet"].values]
        # リストにない弾数がデータ内にある場合も考慮
        other_bullets = [b for b in data["bullet"].dropna().unique() if b not in BULLET_OPTIONS]
        all_bullet_choices = ["すべて"] + existing_bullets + other_bullets
        
        selected_bullet = st.sidebar.selectbox("弾数で絞り込み", all_bullet_choices)
        search_keyword = st.sidebar.text_input("コーデ名・キャラ名で検索")

        # フィルタリング処理
        filtered_data = data.copy()
        if selected_bullet != "すべて":
            filtered_data = filtered_data[filtered_data["bullet"] == selected_bullet]
        if search_keyword:
            filtered_data = filtered_data[
                filtered_data["code_name"].str.contains(search_keyword, na=False) |
                filtered_data["character"].str.contains(search_keyword, na=False)
            ]

        st.write(f"全 **{len(data)}** 枚中 / 表示件数: **{len(filtered_data)}** 枚")

        cols_per_row = 3
        
        # 画面をグリッド状にレイアウト
        for idx, (i, row) in enumerate(filtered_data.iterrows()):
            if idx % cols_per_row == 0:
                col = st.columns(cols_per_row)
            
            with col[idx % cols_per_row]:
                st.markdown(f"### {row['code_name']}")
                if pd.notna(row["image_path"]) and os.path.exists(row["image_path"]):
                    st.image(row["image_path"], use_container_width=True)
                else:
                    st.warning("画像なし")
                
                st.write(f"🏷️ **弾数:** {row['bullet']}")
                st.write(f"🎤 **キャラクター:** {row['character']}")
                
                # 削除ボタン
                if st.button(f"削除 (ID: {int(row['id'])})", key=f"del_{row['id']}"):
                    data = data[data["id"] != row["id"]]
                    data.to_csv(DATA_FILE, index=False)
                    st.success("削除しました！画面を更新してください。")
                    st.rerun()
                st.markdown("---")

# ---------------------------------------------------------
# 2. プリフォト追加画面
# ---------------------------------------------------------
elif menu == "プリフォトを追加する":
    st.header("📸 新しいプリフォトの登録")

    # セッションステートを使って入力値を保持（ファイル名自動反映のため）
    if "code_name_input" not in st.session_state:
        st.session_state["code_name_input"] = ""

    # 画像アップロードをフォームの外に置くことで、ファイル名を即座に読み込めるようにする
    uploaded_image = st.file_uploader("プリフォトの画像 (スマホの写真など)", type=["jpg", "png", "jpeg"])

    # 画像がアップロードされた場合、ファイル名をコーデ名にするボタンを表示
    if uploaded_image is not None:
        # 拡張子を除いたファイル名を取得
        file_base_name = os.path.splitext(uploaded_image.name)[0]
        st.info(f"📁 アップロードされたファイル名: `{uploaded_image.name}`")
        if st.button("✨ ファイル名をコーデ名として使う"):
            st.session_state["code_name_input"] = file_base_name
            st.rerun()

    with st.form("add_form", clear_on_submit=True):
        code_name = st.text_input("コーデ名", value=st.session_state["code_name_input"])
        
        # 弾数をラジオボタン（選択肢形式）に変更
        bullet = st.radio("弾数を選択", BULLET_OPTIONS, horizontal=True)
        
        character = st.text_input("映っているキャラクター名 (マイキャラ / アニメキャラ名)")

        submitted = st.form_submit_button("登録する")

        if submitted:
            if not code_name:
                st.error("コーデ名を入力してください。")
            else:
                # 一意のIDを生成
                new_id = int(data["id"].max() + 1) if not data.empty and not pd.isna(data["id"].max()) else 1
                
                image_path = ""
                if uploaded_image is not None:
                    image_path = os.path.join(IMAGE_DIR, f"card_{new_id}.png")
                    img = Image.open(uploaded_image)
                    img.save(image_path)

                # 新しいデータを追加
                new_row = pd.DataFrame({
                    "id": [new_id],
                    "code_name": [code_name],
                    "bullet": [bullet],
                    "character": [character],
                    "image_path": [image_path]
                })

                data = pd.concat([data, new_row], ignore_index=True)
                data.to_csv(DATA_FILE, index=False)
                
                # 入力保持用をクリア
                st.session_state["code_name_input"] = ""
                st.success("✨ プリフォトを正常に登録しました！")