#!/bin/bash

# Windows環境でビルドするためのファイルをZIPにまとめるスクリプト

# 色付きメッセージ
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# プロジェクト名とZIPファイル名
PROJECT_NAME="FleDjSON"
DATE=$(date +%Y%m%d_%H%M%S)
ZIP_NAME="${PROJECT_NAME}-windows-build-${DATE}.zip"

echo -e "${BLUE}[BUILD] Creating Windows build package...${NC}"

# 一時ディレクトリを作成
TEMP_DIR="temp_windows_build"
rm -rf $TEMP_DIR
mkdir -p $TEMP_DIR/$PROJECT_NAME

echo -e "${GREEN}[OK] Created temporary directory${NC}"

# 必要なファイルとディレクトリをコピー
echo -e "${BLUE}[COPY] Copying source files...${NC}"

# ソースコード
cp -r src $TEMP_DIR/$PROJECT_NAME/
cp -r tests $TEMP_DIR/$PROJECT_NAME/

# プロジェクト設定ファイル
cp pyproject.toml $TEMP_DIR/$PROJECT_NAME/
cp poetry.lock $TEMP_DIR/$PROJECT_NAME/
cp pytest.ini $TEMP_DIR/$PROJECT_NAME/

# ビルドスクリプト
cp win-pyinstaller-build.py $TEMP_DIR/$PROJECT_NAME/

# ドキュメント
cp README.md $TEMP_DIR/$PROJECT_NAME/
cp LICENSE.md $TEMP_DIR/$PROJECT_NAME/
cp -r docs $TEMP_DIR/$PROJECT_NAME/

# プロジェクトメモリとClaude設定
cp Project.md $TEMP_DIR/$PROJECT_NAME/
cp CLAUDE.md $TEMP_DIR/$PROJECT_NAME/

# 初期化ファイル
cp __init__.py $TEMP_DIR/$PROJECT_NAME/

echo -e "${GREEN}[OK] Source files copied${NC}"

# Windows用のREADMEを作成
cat > $TEMP_DIR/$PROJECT_NAME/WINDOWS_BUILD_README.md << 'EOF'
# FleDjSON Windows ビルド手順

## 必要な環境
- Python 3.12以上
- Poetry
- Windows 10/11

## セットアップ手順

### 1. Poetryのインストール（未インストールの場合）
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

### 2. 依存関係のインストール
```powershell
cd FleDjSON
poetry install
```

### 3. ビルド方法

#### 方法A: Flet公式ビルドコマンド（推奨）
```powershell
poetry run flet build windows
```

#### 方法B: PyInstallerスクリプトを使用
```powershell
poetry run python win-pyinstaller-build.py
```

#### 方法C: PyInstallerでFletビルドメソッドを使用
```powershell
poetry run python win-pyinstaller-build.py --method flet
```

### 4. ビルド結果
- Flet build: `build/windows/` ディレクトリに出力
- PyInstaller: `dist/` ディレクトリに出力

## トラブルシューティング

### 画面が真っ白になる場合
1. `src/main.py` に `assets_dir="assets"` が設定されているか確認
2. PyInstallerの場合、specファイルでデータファイルが含まれているか確認

### エラーが出る場合
1. Python 3.12以上がインストールされているか確認
2. すべての依存関係が正しくインストールされているか確認
3. ビルド前に以下を実行:
   ```powershell
   Remove-Item -Recurse -Force build, dist
   ```

## アイコンについて
- アイコンファイルは `src/assets/icon_windows.ico` に配置済み
- 必要に応じて独自のアイコンに置き換え可能
EOF

echo -e "${GREEN}[OK] Created Windows build README${NC}"

# .gitignoreに記載されているファイルを除外
echo -e "${YELLOW}[WARNING] Excluding files from .gitignore...${NC}"
find $TEMP_DIR -name "*.pyc" -delete
find $TEMP_DIR -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find $TEMP_DIR -name ".DS_Store" -delete
rm -rf $TEMP_DIR/$PROJECT_NAME/build
rm -rf $TEMP_DIR/$PROJECT_NAME/dist
rm -rf $TEMP_DIR/$PROJECT_NAME/logs
rm -rf $TEMP_DIR/$PROJECT_NAME/.pytest_cache

# ZIPファイルを作成
echo -e "${BLUE}📦 Creating ZIP file...${NC}"
cd $TEMP_DIR
zip -r ../$ZIP_NAME $PROJECT_NAME -x "*.DS_Store" "*__pycache__*" "*.pyc"
cd ..

# 一時ディレクトリを削除
rm -rf $TEMP_DIR

# ファイルサイズを表示
SIZE=$(du -h $ZIP_NAME | cut -f1)
echo -e "${GREEN}[OK] Successfully created: ${YELLOW}$ZIP_NAME${GREEN} (Size: $SIZE)${NC}"

# ファイル内容の概要を表示
echo -e "\n${BLUE}[INFO] Package contents:${NC}"
unzip -l $ZIP_NAME | grep -E "(src/|tests/|\.py$|\.md$|\.toml$)" | head -20
echo "... and more"

echo -e "\n${GREEN}[COMPLETE] Windows build package is ready!${NC}"
echo -e "${YELLOW}Transfer this file to your Windows machine and follow the instructions in WINDOWS_BUILD_README.md${NC}"