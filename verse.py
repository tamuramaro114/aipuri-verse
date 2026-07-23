import pandas as pd
from PIL import Image
import streamlit as st
import os
import io
import base64

# データの保存先ファイル
DATA_FILE = "aipri_data.csv"

# データの読み込み関数
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["id", "code_name", "bullet", "attribute", "character", "image_base64"])

data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio("選択してください", ["コレクション一覧・検索", "プリフォトを追加する"])

# 弾数の選択肢リスト
BULLET_OPTIONS = []
for i in range(1, 7):
    BULLET_OPTIONS.append(f"{i}だん")
for i in range(1, 7):
    BULLET_OPTIONS.append(f"リング{i}だん")
for i in range(1, 7):
    BULLET_OPTIONS.append(f"おねがい{i}だん")

# 属性の選択肢リスト
ATTRIBUTE_OPTIONS = ["つうじょう", "プリティー", "特殊", "チャンスコーデ"]

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
        other_bullets = [b for b in data["bullet"].dropna().unique() if b not in BULLET_OPTIONS]
        all_bullet_choices = ["すべて"] + existing_bullets + other_bullets
        
        selected_bullet = st.sidebar.selectbox("弾数で絞り込み", all_bullet_choices)
        
        # 属性での絞り込み
        existing_attrs = [a for a in ATTRIBUTE_OPTIONS if "attribute" in data.columns and a in data["attribute"].values]
        all_attr_choices = ["すべて"] + existing_attrs
        selected_attr = st.sidebar.selectbox("属性で絞り込み", all_attr_choices)
        
        search_keyword = st.sidebar.text_input("コーデ名・キャラ名で検索")

        # フィルタリング処理
        filtered_data = data.copy()
        if selected_bullet != "すべて":
            filtered_data = filtered_data[filtered_data["bullet"] == selected_bullet]
        if selected_attr != "すべて" and "attribute" in filtered_data.columns:
            filtered_data = filtered_data[filtered_data["attribute"] == selected_attr]
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
                
                # Base64形式の画像をデコードして表示
                if pd.notna(row["image_base64"]) and row["image_base64"] != "":
                    try:
                        image_bytes = base64.b64decode(row["image_base64"])
                        st.image(image_bytes, use_container_width=True)
                    except:
                        st.warning("画像読み込みエラー")
                else:
                    st.warning("画像なし")
                
                st.write(f"🏷️ **弾数:** {row['bullet']}")
                if "attribute" in row and pd.notna(row["attribute"]):
                    st.write(f"⭐ **属性:** {row['attribute']}")
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

    if "code_name_input" not in st.session_state:
        st.session_state["code_name_input"] = ""

    uploaded_image = st.file_uploader("プリフォトの画像 (スマホの写真など)", type=["jpg", "png", "jpeg"])

    if uploaded_image is not None:
        file_base_name = os.path.splitext(uploaded_image.name)[0]
        st.info(f"📁 アップロードされたファイル名: `{uploaded_image.name}`")
        if st.button("✨ ファイル名をコーデ名として使う"):
            st.session_state["code_name_input"] = file_base_name
            st.rerun()

    with st.form("add_form", clear_on_submit=True):
        code_name = st.text_input("コーデ名", value=st.session_state["code_name_input"])
        
        # 弾数の選択（ラジオボタン）
        bullet = st.radio("弾数を選択", BULLET_OPTIONS, horizontal=True)
        
        # 属性の選択（ラジオボタン）
        attribute = st.radio("属性を選択", ATTRIBUTE_OPTIONS, horizontal=True)
        
        character = st.text_input("映っているキャラクター名 (マイキャラ / アニメキャラ名)")

        submitted = st.form_submit_button("登録する")

        if submitted:
            if not code_name:
                st.error("コーデ名を入力してください。")
            else:
                new_id = int(data["id"].max() + 1) if not data.empty and not pd.isna(data["id"].max()) else 1
                
                image_base64 = ""
                if uploaded_image is not None:
                    # 画像を読み込んでBase64文字列に変換
                    bytes_data = uploaded_image.getvalue()
                    image_base64 = base64.b64encode(bytes_data).decode("utf-8")

                # 新しいデータを追加
                new_row = pd.DataFrame({
                    "id": [new_id],
                    "code_name": [code_name],
                    "bullet": [bullet],
                    "attribute": [attribute],
                    "character": [character],
                    "image_base64": [image_base64]
                })

                data = pd.concat([data, new_row], ignore_index=True)
                data.to_csv(DATA_FILE, index=False)
                
                st.session_state["code_name_input"] = ""
                st.success("✨ プリフォトを正常に登録しました！")