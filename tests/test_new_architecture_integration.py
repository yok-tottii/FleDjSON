"""
新アーキテクチャの統合テスト
TemplateManager、CopyManager、FlattenManagerの統合テスト
"""
import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

# Import test fixtures
from .conftest import sample_json_data, sample_app_state, ui_controls, temp_dir

# Import all managers for integration testing
from src.managers.template_manager import TemplateManager
from src.managers.copy_manager import CopyManager
from src.managers.flatten_manager import FlattenManager
from src.managers.data_manager import DataManager
from src.managers.form_manager import FormManager
from src.managers.ui_manager import UIManager
from src.managers.search_manager import SearchManager
from src.managers.analysis_manager import AnalysisManager
from src.managers.ui_state_manager import UIStateManager

# Import event system
from src.event_hub import EventHub, EventType
from src.error_handling import ErrorHandler
from src.feedback import FeedbackManager


@pytest.fixture
def integrated_new_managers(sample_app_state, ui_controls, temp_dir):
    """新マネージャークラスを含む完全な統合環境を作成"""
    # Set up the app directory
    sample_app_state["app_dir"] = temp_dir
    
    # Create event hub
    event_hub = EventHub()
    sample_app_state["event_hub"] = event_hub
    
    # Create all managers
    data_manager = DataManager(sample_app_state, ui_controls, ui_controls.get("page"))
    form_manager = FormManager(ui_controls, sample_app_state)
    ui_manager = UIManager(ui_controls, sample_app_state)
    search_manager = SearchManager(ui_controls, sample_app_state)
    template_manager = TemplateManager(sample_app_state, ui_controls, ui_controls.get("page"), event_hub)
    copy_manager = CopyManager(sample_app_state, ui_controls, ui_controls.get("page"), event_hub)
    flatten_manager = FlattenManager(sample_app_state, ui_controls, ui_controls.get("page"), event_hub)
    analysis_manager = AnalysisManager(sample_app_state, ui_controls, ui_controls.get("page"))
    ui_state_manager = UIStateManager(sample_app_state, ui_controls, ui_controls.get("page"))
    
    # Error and feedback systems
    error_handler = ErrorHandler(sample_app_state, ui_controls, ui_controls.get("page"))
    feedback_manager = FeedbackManager(ui_controls, sample_app_state)
    
    # Store all components in app_state
    managers = {
        "data_manager": data_manager,
        "form_manager": form_manager,
        "ui_manager": ui_manager,
        "search_manager": search_manager,
        "template_manager": template_manager,
        "copy_manager": copy_manager,
        "flatten_manager": flatten_manager,
        "analysis_manager": analysis_manager,
        "ui_state_manager": ui_state_manager,
        "error_handler": error_handler,
        "feedback_manager": feedback_manager
    }
    
    for key, manager in managers.items():
        sample_app_state[key] = manager
    
    # Connect event-aware managers to event hub
    for manager in [data_manager, form_manager, ui_manager, search_manager, ui_state_manager, feedback_manager]:
        if hasattr(manager, 'connect_to_event_hub'):
            manager.connect_to_event_hub()
    
    return {
        "event_hub": event_hub,
        "managers": managers,
        "app_state": sample_app_state,
        "ui_controls": ui_controls
    }


@pytest.mark.integration
class TestNewManagersIntegration:
    """新マネージャークラスの統合テスト"""

    def test_template_manager_integration(self, integrated_new_managers, temp_dir):
        """TemplateManagerの統合テスト"""
        managers = integrated_new_managers["managers"]
        template_manager = managers["template_manager"]
        data_manager = managers["data_manager"]
        form_manager = managers["form_manager"]
        
        # サンプルデータ作成
        sample_data = {
            "id": 1,
            "name": "John Doe",
            "profile": {
                "age": 30,
                "email": "john@example.com"
            },
            "tags": ["developer", "python"]
        }
        
        # テンプレート生成
        template = template_manager.generate_template(sample_data)
        
        # テンプレートの構造確認
        assert isinstance(template, dict)
        assert len(template) > 0
        
        # テンプレートにフィールドが含まれていることを確認
        if "id" in template:
            assert "field_type" in template["id"] or "type" in template["id"]
        if "name" in template:
            assert "field_type" in template["name"] or "type" in template["name"]
        if "profile" in template:
            assert "field_type" in template["profile"] or "type" in template["profile"]
        
        # データマネージャーにデータ設定
        data_manager.current_data = sample_data
        
        # テンプレートを使用した新規ノード作成
        initial_values = {"id": 2, "name": "Jane Smith"}
        new_node = template_manager.apply_template(template, initial_values)
        
        # 新規ノードの構造確認
        assert new_node["id"] == 2
        assert new_node["name"] == "Jane Smith"
        assert "profile" in new_node
        assert isinstance(new_node["profile"], dict)

    def test_copy_manager_integration(self, integrated_new_managers):
        """CopyManagerの統合テスト"""
        managers = integrated_new_managers["managers"]
        copy_manager = managers["copy_manager"]
        data_manager = managers["data_manager"]
        
        # 配列参照問題があるサンプルデータ
        original_data = {
            "users": [
                {"id": 1, "tags": ["admin", "active"]},
                {"id": 2, "tags": ["user"]}
            ]
        }
        
        data_manager.current_data = original_data
        
        # 深いコピーを実行
        copied_data = copy_manager.safe_deep_copy(original_data)
        
        # コピーの独立性確認
        copied_data["users"][0]["tags"].append("test")
        
        # 元データが変更されていないことを確認
        assert len(original_data["users"][0]["tags"]) == 2
        assert len(copied_data["users"][0]["tags"]) == 3
        assert "test" not in original_data["users"][0]["tags"]
        assert "test" in copied_data["users"][0]["tags"]

    def test_flatten_manager_integration(self, integrated_new_managers):
        """FlattenManagerの統合テスト"""
        managers = integrated_new_managers["managers"]
        flatten_manager = managers["flatten_manager"]
        data_manager = managers["data_manager"]
        
        # ネスト構造のサンプルデータ
        nested_data = {
            "user": {
                "profile": {
                    "personal": {
                        "name": "John",
                        "age": 30
                    },
                    "contact": {
                        "email": "john@example.com"
                    }
                },
                "settings": ["dark_mode", "notifications"]
            }
        }
        
        data_manager.current_data = nested_data
        
        # 平坦化実行
        flattened, success = flatten_manager.try_flatten_json(nested_data)
        
        # 平坦化が成功したことを確認
        assert success is True
        assert isinstance(flattened, list)
        assert len(flattened) > 0
        
        # 基本的な構造確認（FlattenManagerは階層を平坦化するが実際の構造は実装に依存）
        # データが正常に処理されたことを確認
        flattened_data = flattened[0] if flattened else {}
        if isinstance(flattened_data, dict):
            # 何らかのデータが含まれていることを確認
            assert len(flattened_data) > 0

    def test_managers_event_integration(self, integrated_new_managers, temp_dir):
        """マネージャー間のイベント連携テスト"""
        event_hub = integrated_new_managers["event_hub"]
        managers = integrated_new_managers["managers"]
        
        # サンプルファイル作成
        test_file = os.path.join(temp_dir, "integration_test.json")
        test_data = {
            "id": 1,
            "name": "Integration Test",
            "data": {"value": "test"}
        }
        
        with open(test_file, "w") as f:
            json.dump(test_data, f)
        
        # Form Managerにイベントリスナー追加
        form_events_received = []
        def mock_form_listener(event_data):
            form_events_received.append(event_data)
        
        # UI Managerにイベントリスナー追加
        ui_events_received = []
        def mock_ui_listener(event_data):
            ui_events_received.append(event_data)
        
        # イベント購読設定
        event_hub.subscribe(EventType.DATA_LOADED, mock_form_listener)
        event_hub.subscribe(EventType.DATA_LOADED, mock_ui_listener)
        
        # データロードイベント発火
        managers["data_manager"].load_json_file(test_file)
        
        # イベント伝播を待つ
        import time
        time.sleep(0.1)
        
        # イベント受信確認
        assert len(form_events_received) >= 1
        assert len(ui_events_received) >= 1

    def test_field_order_preservation_integration(self, integrated_new_managers):
        """フィールド順序保持機能の統合テスト"""
        managers = integrated_new_managers["managers"]
        form_manager = managers["form_manager"]
        data_manager = managers["data_manager"]
        
        # 入力順序のテストデータ
        form_manager.track_key("id")
        form_manager.track_key("profile.bio") 
        form_manager.track_key("profile.age")
        form_manager.track_key("tags[0]")
        form_manager.track_key("contact.email")
        
        # 編集バッファに値を設定
        app_state = integrated_new_managers["app_state"]
        app_state["edit_buffer"] = {
            "id": "test-001",
            "profile.bio": "Software Developer",
            "profile.age": 28,
            "tags[0]": "python",
            "contact.email": "test@example.com"
        }
        
        # 順序付きキーを取得
        sorted_keys = form_manager.sort_edit_buffer_keys()
        
        # 入力順序が保持されていることを確認
        expected_order = ["id", "profile.bio", "profile.age", "tags[0]", "contact.email"]
        assert sorted_keys == expected_order

    def test_error_recovery_across_managers(self, integrated_new_managers, temp_dir):
        """マネージャー間のエラー回復テスト"""
        managers = integrated_new_managers["managers"]
        app_state = integrated_new_managers["app_state"]
        
        error_handler = managers["error_handler"]
        copy_manager = managers["copy_manager"]
        template_manager = managers["template_manager"]
        
        # 無効なデータでテンプレート作成を試行
        invalid_data = "not a dictionary"
        
        # エラーハンドリングのモック
        error_events = []
        def mock_error_handler(error):
            error_events.append(error)
            # Copy Managerを使用した回復アクション
            if hasattr(error, 'add_recovery_action'):
                def recovery_action():
                    return copy_manager.deep_copy({"id": "default", "name": "Default"})
                error.add_recovery_action("use_default", "デフォルトデータを使用", recovery_action)
        
        # エラーハンドラーにモック設定
        with patch.object(error_handler, 'handle_error', side_effect=mock_error_handler):
            try:
                template = template_manager.create_template_from_data(invalid_data)
            except Exception as e:
                error_handler.handle_error(e)
        
        # エラーが適切に処理されたことを確認
        assert len(error_events) >= 1
        
        # 回復アクションが利用可能であることを確認
        if error_events and hasattr(error_events[0], 'recovery_actions'):
            assert "use_default" in error_events[0].recovery_actions


@pytest.mark.e2e
class TestEndToEndNewArchitecture:
    """新アーキテクチャでのEnd-to-Endテスト"""

    def test_complete_workflow_with_new_managers(self, integrated_new_managers, temp_dir):
        """新マネージャーを含む完全なワークフローテスト"""
        managers = integrated_new_managers["managers"]
        event_hub = integrated_new_managers["event_hub"]
        
        # Step 1: テストデータ作成とロード
        test_file = os.path.join(temp_dir, "workflow_test.json")
        source_data = {
            "users": [
                {
                    "id": 1,
                    "name": "John Doe",
                    "profile": {"age": 30, "role": "developer"},
                    "tags": ["python", "flask"]
                },
                {
                    "id": 2,
                    "name": "Jane Smith", 
                    "profile": {"age": 25, "role": "designer"},
                    "tags": ["ui", "ux"]
                }
            ]
        }
        
        with open(test_file, "w") as f:
            json.dump(source_data, f)
        
        managers["data_manager"].load_json_file(test_file)
        
        # Step 2: テンプレート生成
        template = managers["template_manager"].create_template_from_data(source_data["users"][0])
        
        # Step 3: 平坦化でデータ分析
        flattened = managers["flatten_manager"].flatten_json(source_data)
        user_fields = [k for k in flattened.keys() if k.startswith("users[0]")]
        
        # Step 4: 新ユーザーをテンプレートから作成（CopyManagerで安全性確保）
        new_user_template = managers["copy_manager"].deep_copy(template)
        new_user = managers["template_manager"].apply_template(
            new_user_template, 
            {"id": 3, "name": "Bob Johnson"}
        )
        
        # Step 5: フィールド順序保持でフォーム更新
        form_manager = managers["form_manager"]
        form_manager.track_key("id")
        form_manager.track_key("name")
        form_manager.track_key("profile.age")
        form_manager.track_key("profile.role")
        
        # Step 6: 検証
        assert new_user["id"] == 3
        assert new_user["name"] == "Bob Johnson"
        assert "profile" in new_user
        assert isinstance(new_user["profile"], dict)
        
        # テンプレートが独立していることを確認
        assert new_user is not template
        assert new_user["profile"] is not template["profile"]
        
        # 平坦化データに期待されるフィールドが含まれていることを確認
        assert "users[0].id" in flattened
        assert "users[0].name" in flattened
        assert "users[0].profile.age" in flattened
        
        # フィールド順序が保持されていることを確認
        app_state = integrated_new_managers["app_state"]
        app_state["edit_buffer"] = {
            "id": 3,
            "name": "Bob Johnson",
            "profile.age": 28,
            "profile.role": "tester"
        }
        
        sorted_keys = form_manager.sort_edit_buffer_keys()
        expected_order = ["id", "name", "profile.age", "profile.role"]
        assert sorted_keys == expected_order

    def test_memory_safety_integration(self, integrated_new_managers):
        """メモリ安全性の統合テスト（配列参照問題の解決確認）"""
        managers = integrated_new_managers["managers"]
        copy_manager = managers["copy_manager"]
        data_manager = managers["data_manager"]
        
        # 共有配列参照問題を引き起こしやすいデータ構造
        shared_config = ["setting1", "setting2"]
        original_data = {
            "user1": {"config": shared_config},
            "user2": {"config": shared_config},  # 同じ配列参照
            "global_settings": shared_config       # 同じ配列参照
        }
        
        # データマネージャーに設定
        data_manager.current_data = original_data
        
        # 深いコピーで独立したデータ作成
        independent_data = copy_manager.deep_copy(original_data)
        
        # 独立性テスト
        independent_data["user1"]["config"].append("new_setting1")
        independent_data["user2"]["config"].append("new_setting2")
        independent_data["global_settings"].append("new_global")
        
        # 元データが変更されていないことを確認
        assert len(original_data["user1"]["config"]) == 2
        assert len(original_data["user2"]["config"]) == 2
        assert len(original_data["global_settings"]) == 2
        
        # コピーされたデータが独立して変更されたことを確認
        assert "new_setting1" in independent_data["user1"]["config"]
        assert "new_setting2" in independent_data["user2"]["config"]
        assert "new_global" in independent_data["global_settings"]
        
        # 元データには新しい設定が含まれていないことを確認
        assert "new_setting1" not in original_data["user1"]["config"]
        assert "new_setting2" not in original_data["user2"]["config"]
        assert "new_global" not in original_data["global_settings"]

    def test_performance_with_large_data(self, integrated_new_managers):
        """大量データでのパフォーマンステスト"""
        managers = integrated_new_managers["managers"]
        
        # 大量のネストデータ作成
        large_data = {}
        for i in range(100):
            large_data[f"category_{i}"] = {
                "items": [
                    {
                        "id": j,
                        "name": f"item_{i}_{j}",
                        "metadata": {
                            "tags": [f"tag_{k}" for k in range(5)],
                            "properties": {f"prop_{k}": f"value_{k}" for k in range(3)}
                        }
                    }
                    for j in range(10)
                ]
            }
        
        # パフォーマンステスト
        import time
        
        # 平坦化パフォーマンス
        start_time = time.time()
        flattened = managers["flatten_manager"].flatten_json(large_data)
        flatten_time = time.time() - start_time
        
        # コピーパフォーマンス
        start_time = time.time()
        copied = managers["copy_manager"].deep_copy(large_data)
        copy_time = time.time() - start_time
        
        # テンプレート生成パフォーマンス（最初のアイテムのみ）
        first_item = large_data["category_0"]["items"][0]
        start_time = time.time()
        template = managers["template_manager"].create_template_from_data(first_item)
        template_time = time.time() - start_time
        
        # パフォーマンス要件確認（各操作が5秒以内に完了）
        assert flatten_time < 5.0, f"平坦化に{flatten_time:.2f}秒かかりました"
        assert copy_time < 5.0, f"コピーに{copy_time:.2f}秒かかりました"
        assert template_time < 1.0, f"テンプレート生成に{template_time:.2f}秒かかりました"
        
        # 結果の健全性確認
        assert len(flattened) > 1000  # 十分な数のキーが平坦化されている
        assert copied is not large_data  # 異なるオブジェクト
        assert len(template) > 0  # テンプレートが生成されている

    def test_concurrent_operations_safety(self, integrated_new_managers):
        """同時操作での安全性テスト"""
        managers = integrated_new_managers["managers"]
        copy_manager = managers["copy_manager"]
        
        # 同時アクセスされる可能性があるデータ
        shared_data = {
            "counter": 0,
            "items": [],
            "status": "active"
        }
        
        # 複数の操作を並行実行（モック）
        operations = []
        for i in range(5):
            copied = copy_manager.deep_copy(shared_data)
            copied["counter"] = i
            copied["items"].append(f"item_{i}")
            operations.append(copied)
        
        # 各操作が独立していることを確認
        for i, operation in enumerate(operations):
            assert operation["counter"] == i
            assert len(operation["items"]) == 1
            assert f"item_{i}" in operation["items"]
            
            # 他の操作のデータが混入していないことを確認
            for j, other_operation in enumerate(operations):
                if i != j:
                    assert operation is not other_operation
                    assert operation["items"] is not other_operation["items"]