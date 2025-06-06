# FleDjSON 公開ドキュメント

このディレクトリには、FleDjSONの公開ドキュメントとサンプルデータが含まれています。

## ドキュメント構造

### 📖 公開ドキュメント
- **genericity_verification.md** - FleDjSONの汎用性設計思想の検証文書
- **examples/** - サンプルJSONファイル集

### 🔒 内部開発文書
内部開発用の分析レポートや設計文書は `docs-internal/` ディレクトリに移動されています：
- アーキテクチャ分析レポート
- 開発フェーズレポート  
- マネージャーカバレッジ分析
- モジュール比較分析

## サンプルファイル

FleDjSONの機能をテストするための様々なJSONデータを提供しています：

- **sample-data.json** - 基本的なツリー構造のJSONデータ
- **sample-data2.json** - 追加のサンプルデータ  
- **sample-data3.json** - 別の形式のサンプルデータ
- **complex_nested_structure.json** - 複雑に入れ子になったJSONオブジェクト
- **large_tree_test.json** - 大量のノードを含む大規模ツリー構造
- **test.json** - シンプルなテスト用データ

## 使用方法

1. FleDjSONアプリケーションを起動
2. これらのサンプルファイルをロード
3. 表示、編集、保存などの操作をテスト
4. 新機能やバグ確認に活用

## FleDjSONの設計思想

FleDjSONは「**特定の構造やキーに依存しないように細心の注意を払って実装**」されています。
詳細は `genericity_verification.md` をご覧ください。

## 技術仕様

- **アーキテクチャ**: クラスベース設計
- **フレームワーク**: Flet (Python GUI)
- **特徴**: 汎用性、型推論、パターン認識
- **対応**: デスクトップ、モバイル、Web

FleDjSONは任意のJSON構造に対して、動的な分析とパターン認識により、
適切なユーザーインターフェースを自動生成します。