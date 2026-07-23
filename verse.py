import pandas as pd
from PIL import Image
import streamlit as st
import os
import io
import base64

# データの保存先ファイル
DATA_FILE = "aipri_data.csv"

# データの読み込み関数（古いデータに部位カラムがない場合のエラー防止のため初期値を追加）
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if "part" not in df.columns:
            df["part"] = "ワンピース" # 既存データ用のデフォルト
        return df
    else:
        return pd.DataFrame(columns=["id", "code_name", "bullet", "attribute", "part", "character", "image_base64"])

data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio("選択してください", ["コレクション一覧・検索", "プリフォトを追加する"])

# 通常の弾数の選択肢リスト
NORMAL_BULLET_OPTIONS = []
for i in range(1, 7):
    NORMAL_BULLET_OPTIONS.append(f"{i}だん")
for i in range(1, 7):
    NORMAL_BULLET_OPTIONS.append(f"リング{i}だん")
for i in range(1, 7):
    NORMAL_BULLET_OPTIONS.append(f"おねがい{i}だん")

# ミルフィー用の弾数の選択肢リスト
MILLEFEE_BULLET_OPTIONS = [
    "vol.1", "vol.2", "vol.3", 
    "Rvol.1", "Rvol.2", "Rvol.3", 
    "おねがいvol.1", "おねがいvol.2"
]

ALL_BULLET_OPTIONS = NORMAL_BULLET_OPTIONS + MILLEFEE_BULLET_OPTIONS

# 属性の選択肢リスト
ATTRIBUTE_OPTIONS = ["つうじょう", "プリティー", "特殊", "チャンスコーデ", "コラボ", "フルコーデ", "ミルフィー"]

# コーデの部位の選択肢リスト
PART_OPTIONS = ["アクセ", "ワンピース", "トップス", "ボトムス", "シューズ"]

# 部位の並び順を決めるための辞書（アクセ → 服系 → シューズ）
PART_SORT_ORDER = {
    "アクセ": 1,
    "ワンピース": 2,
    "トップス": 3,
    "ボトムス": 4,
    "シューズ": 5
}

# ---------------------------------------------------------
# 1. コレクション一覧・検索画面
# ---------------------------------------------------------
if menu == "コレクション一覧・検索":
    st.header("📖 マイ・プリフォトコレクション")

    if data.empty:
        st.info("まだプリフォトが登録されていません。「プリフォトを追加する」から登録してみましょう！")
    else:
        # 絞り込みフィルター & 設定
        st.sidebar.subheader("🔍 絞り込み検索 & 設定")
        
        # 並べ替え機能の選択
        sort_option = st.sidebar.selectbox("並べ替え", [
            "コーデ名順 (アクセ→服→靴)", 
            "50音順 (コーデ名)", 
            "弾の早い順 (昇順)", 
            "弾の遅い順 (降順)", 
            "登録順 (新しい順)", 
            "登録順 (古い順)"
        ])
        
        # 横一列に表示する数を変更できるスライダー
        cols_per_row = st.sidebar.slider("横に並べるカードの数", min_value=2, max_value=6, value=3)

        existing_bullets = [b for b in ALL_BULLET_OPTIONS if b in data["bullet"].values]
        other_bullets = [b for b in data["bullet"].dropna().unique() if b not in ALL_BULLET_OPTIONS]
        all_bullet_choices = ["すべて"] + existing_bullets + other_bullets
        
        selected_bullet = st.sidebar.selectbox("弾数で絞り込み", all_bullet_choices)
        
        # 属性での絞り込み
        existing_attrs = [a for a in ATTRIBUTE_OPTIONS if "attribute" in data.columns and a in data["attribute"].values]
        all_attr_choices = ["すべて"] + existing_attrs
        selected_attr = st.sidebar.selectbox("属性で絞り込み", all_attr_choices)

        # 部位での絞り込み
        existing_parts = [p for p in PART_OPTIONS if "part" in data.columns and p in data["part"].values]
        all_part_choices = ["すべて"] + existing_parts
        selected_part = st.sidebar.selectbox("部位で絞り込み", all_part_choices)
        
        search_keyword = st.sidebar.text_input("コーデ名・キャラ名で検索")

        # フィルタリング処理
        filtered_data = data.copy()
        if selected_bullet != "すべて":
            filtered_data = filtered_data[filtered_data["bullet"] == selected_bullet]
        if selected_attr != "すべて" and "attribute" in filtered_data.columns:
            filtered_data = filtered_data[filtered_data["attribute"] == selected_attr]
        if selected_part != "すべて" and "part" in filtered_data.columns:
            filtered_data = filtered_data[filtered_data["part"] == selected_part]
        if search_keyword:
            filtered_data = filtered_data[
                filtered_data["code_name"].str.contains(search_keyword, na=False) |
                filtered_data["character"].str.contains(search_keyword, na=False)
            ]

        # --- 並べ替え（ソート）処理 ---
        # 部位の順番を数値化して一時列に追加
        filtered_data["part_sort_val"] = filtered_data["part"].map(PART_SORT_ORDER).fillna(99)

        if sort_option == "コーデ名順 (アクセ→服→靴)":
            # コーデ名で並べたあと、同じコーデ名の中では アクセ→服→靴 の順にする
            filtered_data = filtered_data.sort_values(by=["code_name", "part_sort_val"], ascending=[True, True])
        elif sort_option == "50音順 (コーデ名)":
            filtered_data = filtered_data.sort_values(by="code_name", ascending=True)
        elif sort_option == "弾の早い順 (昇順)":
            filtered_data = filtered_data.sort_values(by="bullet", ascending=True)
        elif sort_option == "弾の遅い順 (降順)":
            filtered_data = filtered_data.sort_values(by="bullet", ascending=False)
        elif sort_option == "登録順 (新しい順)":
            filtered_data = filtered_data.sort_values(by="id", ascending=False)
        elif sort_option == "登録順 (古い順)":
            filtered_data = filtered_data.sort_values(by="id", ascending=True)

        st.write(f"全 **{len(data)}** 枚中 / 表示件数: **{len(filtered_data)}** 枚")

        # 横に並べる数に応じて見出しの文字サイズを動的に変更
        font_sizes = {
            2: "1.5rem",
            3: "1.3rem",
            4: "1.1rem",
            5: "0.95rem",
            6: "0.85rem"
        }
        current_font_size = font_sizes.get(cols_per_row, "1.2rem")

        # 画面をグリッド状にレイアウト
        for idx, (i, row) in enumerate(filtered_data.iterrows()):
            if idx % cols_per_row == 0:
                col = st.columns(cols_per_row)
            
            with col[idx % cols_per_row]:
                st.markdown(f"<p style='font-size: {current_font_size}; font-weight: bold; margin-bottom: 0.5rem;'>{row['code_name']}</p>", unsafe_allow_html=True)
                
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
                if "part" in row and pd.notna(row["part"]):
                    st.write(f"👗 **部位:** {row['part']}")
                st.write(f"🎤 **キャラクター:** {row['character']}")
                
                # 編集・削除ボタンを横並びに配置
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    edit_key = f"edit_mode_{row['id']}"
                    if st.button("編集", key=f"btn_edit_{row['id']}"):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                
                with btn_col2:
                    if st.button("削除", key=f"del_{row['id']}"):
                        data = data[data["id"] != row["id"]]
                        data.to_csv(DATA_FILE, index=False)
                        st.success("削除しました！画面を更新してください。")
                        st.rerun()

                # 編集フォーム（編集ボタンが押されたら展開される）
                if st.session_state.get(f"edit_mode_{row['id']}", False):
                    with st.form(key=f"form_edit_{row['id']}"):
                        st.markdown("---")
                        st.write("✏️ **内容の編集**")
                        
                        new_code_name = st.text_input("コーデ名", value=row["code_name"])
                        
                        attr_val = row["attribute"] if "attribute" in row and pd.notna(row["attribute"]) else "つうじょう"
                        a_idx = ATTRIBUTE_OPTIONS.index(attr_val) if attr_val in ATTRIBUTE_OPTIONS else 0
                        new_attribute = st.selectbox("属性", ATTRIBUTE_OPTIONS, index=a_idx, key=f"ea_{row['id']}")
                        
                        current_bullets = MILLEFEE_BULLET_OPTIONS if new_attribute == "ミルフィー" else NORMAL_BULLET_OPTIONS
                        b_val = row["bullet"]
                        b_idx = current_bullets.index(b_val) if b_val in current_bullets else 0
                        new_bullet = st.selectbox("弾数", current_bullets, index=b_idx, key=f"eb_{row['id']}")
                        
                        part_val = row["part"] if "part" in row and pd.notna(row["part"]) else "ワンピース"
                        p_idx = PART_OPTIONS.index(part_val) if part_val in PART_OPTIONS else 0
                        new_part = st.selectbox("部位", PART_OPTIONS, index=p_idx, key=f"ep_{row['id']}")
                        
                        char_val = row["character"] if pd.notna(row["character"]) else ""
                        new_character = st.text_input("キャラクター", value=char_val, key=f"ec_{row['id']}")
                        
                        new_image = st.file_uploader("画像を変更する場合のみ選択", type=["jpg", "png", "jpeg"], key=f"ei_{row['id']}")

                        if st.form_submit_button("更新を保存"):
                            data.loc[data["id"] == row["id"], "code_name"] = new_code_name
                            data.loc[data["id"] == row["id"], "bullet"] = new_bullet
                            data.loc[data["id"] == row["id"], "attribute"] = new_attribute
                            data.loc[data["id"] == row["id"], "part"] = new_part
                            data.loc[data["id"] == row["id"], "character"] = new_character
                            
                            if new_image is not None:
                                bytes_data = new_image.getvalue()
                                new_base64 = base64.b64encode(bytes_data).decode("utf-8")
                                data.loc[data["id"] == row["id"], "image_base64"] = new_base64
                            
                            data.to_csv(DATA_FILE, index=False)
                            st.session_state[edit_key] = False
                            st.success("更新しました！画面を更新してください。")
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

    # アップロードされた画像のプレビュー表示
    if uploaded_image is not None:
        file_base_name = os.path.splitext(uploaded_image.name)[0]
        st.info(f"📁 アップロードされたファイル名: `{uploaded_image.name}`")
        
        st.write("🖼️ **登録される画像プレビュー:**")
        st.image(uploaded_image, width=250)

        if st.button("✨ ファイル名をコーデ名として使う"):
            st.session_state["code_name_input"] = file_base_name
            st.rerun()

    with st.form("add_form", clear_on_submit=True):
        code_name = st.text_input("コーデ名", value=st.session_state["code_name_input"])
        
        # 属性の選択（ラジオボタン）
        attribute = st.radio("属性を選択", ATTRIBUTE_OPTIONS, horizontal=True)
        
        # 属性が「ミルフィー」のときは専用の選択肢、それ以外は通常のものに切り替え
        if attribute == "ミルフィー":
            bullet = st.radio("弾数を選択 (ミルフィー)", MILLEFEE_BULLET_OPTIONS, horizontal=True)
        else:
            bullet = st.radio("弾数を選択", NORMAL_BULLET_OPTIONS, horizontal=True)
        
        # 部位の選択（ラジオボタン）
        part = st.radio("部位を選択", PART_OPTIONS, horizontal=True)
        
        character = st.text_input("映っているキャラクター名 (マイキャラ / アニメキャラ名)")

        submitted = st.form_submit_button("登録する")

        if submitted:
            if not code_name:
                st.error("コーデ名を入力してください。")
            else:
                new_id = int(data["id"].max() + 1) if not data.empty and not pd.isna(data["id"].max()) else 1
                
                image_base64 = ""
                if uploaded_image is not None:
                    bytes_data = uploaded_image.getvalue()
                    image_base64 = base64.b64encode(bytes_data).decode("utf-8")

                new_row = pd.DataFrame({
                    "id": [new_id],
                    "code_name": [code_name],
                    "bullet": [bullet],
                    "attribute": [attribute],
                    "part": [part],
                    "character": [character],
                    "image_base64": [image_base64]
                })

                data = pd.concat([data, new_row], ignore_index=True)
                data.to_csv(DATA_FILE, index=False)
                
                st.session_state["code_name_input"] = ""
                st.success("✨ プリフォトを正常に登録しました！")