"""
テスト用の共通フィクスチャと設定を提供するモジュール。
"""
import os
import sys
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# モック最適化コンポーネントを読み込む
from .mock_optimizations import (
    MockLazyJSONLoader,
    MockCachedDataManager,
    MockBackgroundProcessor,
    MockTreeOptimizer
)

# イベントシステムのモックを読み込む
from .mock_event_hub import (
    EventType,
    PriorityLevel,
    MockEventHub,
    MockEventAwareManager
)

# エラーハンドリングのモックを読み込む
from .mock_error_handling import (
    ErrorSeverity,
    ErrorCategory,
    RecoveryAction,
    AppError,
    ErrorHandler,
    with_error_handling
)

# テスト対象のモジュールをインポートする前にFletをモックする
sys.modules['flet'] = MagicMock(name='MockFlet')

# 必要なFletクラスをモック化
class MockControlEvent:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class MockControl:
    def __init__(self, **kwargs):
        self.controls = []
        self.visible = True
        self.id = kwargs.get('id', '')
        self.data = kwargs.get('data', None)
        self.content = kwargs.get('content', None)
        self.bgcolor = kwargs.get('bgcolor', None)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def update(self):
        pass

class MockContainer(MockControl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get('content', None)
        self.alignment = kwargs.get('alignment', None)
        self.padding = kwargs.get('padding', None)
        self.margin = kwargs.get('margin', None)
        self.width = kwargs.get('width', None)
        self.height = kwargs.get('height', None)
        self.border = kwargs.get('border', None)
        self.border_radius = kwargs.get('border_radius', None)
        self.bgcolor = kwargs.get('bgcolor', None)

class MockAppBar(MockControl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = kwargs.get('title', None)
        self.actions = kwargs.get('actions', [])
        self.leading = kwargs.get('leading', None)
        self.center_title = kwargs.get('center_title', False)

class MockDraggable(MockControl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get('content', None)
        self.group = kwargs.get('group', None)
        self.data = kwargs.get('data', None)

class MockDragTarget(MockControl):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get('content', None)
        self.group = kwargs.get('group', None)
        self.data = kwargs.get('data', None)

class MockRef:
    def __init__(self):
        self.current = None

class MockPage:
    def __init__(self):
        self.controls = []
        self.title = "テストアプリケーション"
        self.window_width = 1200
        self.window_height = 800
        self.window_title = "テスト"
        self.padding = 0
        self.bgcolor = "#FFFFFF"
        self.scroll = "auto"
        self.update_interval = 0.1

    def add(self, control):
        self.controls.append(control)

    def update(self):
        pass

    def show_dialog(self, dialog):
        pass

class MockFilePickerResultEvent:
    def __init__(self, files=None, path=None):
        self.files = files or []
        self.path = path
        self.cancelled = False

# Fletモックをグローバル名前空間に定義
sys.modules['flet'].Container = MockContainer
sys.modules['flet'].AppBar = MockAppBar
sys.modules['flet'].Draggable = MockDraggable
sys.modules['flet'].DragTarget = MockDragTarget
sys.modules['flet'].ControlEvent = MockControlEvent
sys.modules['flet'].Page = MockPage
sys.modules['flet'].Ref = MockRef
sys.modules['flet'].FilePickerResultEvent = MockFilePickerResultEvent
sys.modules['flet'].Colors = MagicMock()
sys.modules['flet'].Icons = MagicMock()
sys.modules['flet'].FilePicker = MagicMock()
sys.modules['flet'].ProgressBar = MagicMock()
sys.modules['flet'].TextField = MagicMock()
sys.modules['flet'].Dropdown = MagicMock()
sys.modules['flet'].Text = MagicMock()
sys.modules['flet'].Row = MagicMock()
sys.modules['flet'].Column = MagicMock()
sys.modules['flet'].ElevatedButton = MagicMock()
sys.modules['flet'].IconButton = MagicMock()
sys.modules['flet'].VerticalDivider = MagicMock()
sys.modules['flet'].Divider = MagicMock()
sys.modules['flet'].Card = MagicMock()
sys.modules['flet'].ProgressRing = MagicMock()
sys.modules['flet'].SnackBar = MagicMock()
sys.modules['flet'].Banner = MagicMock()
sys.modules['flet'].ListView = MagicMock()
sys.modules['flet'].ListTile = MagicMock()
sys.modules['flet'].Tab = MagicMock()
sys.modules['flet'].Tabs = MagicMock()
sys.modules['flet'].AlertDialog = MagicMock()
sys.modules['flet'].TextButton = MagicMock()
sys.modules['flet'].Switch = MagicMock()
sys.modules['flet'].Checkbox = MagicMock()
sys.modules['flet'].FloatingActionButton = MagicMock()
sys.modules['flet'].NavigationRail = MagicMock()
sys.modules['flet'].NavigationRailDestination = MagicMock()

# フィクスチャ
@pytest.fixture
def mock_flet():
    """
    Fletモジュールのモックを返す。
    """
    return sys.modules['flet']

@pytest.fixture
def temp_dir():
    """
    一時ディレクトリを作成して返す。
    テスト終了時に自動的に削除される。
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def sample_json_data():
    """
    テスト用のサンプルJSONデータを返す。
    """
    return {
        "string_value": "これはテストです",
        "number_value": 42,
        "boolean_value": True,
        "null_value": None,
        "array_value": [1, 2, 3, 4, 5],
        "object_value": {
            "nested_key": "ネストされた値",
            "another_key": 123
        }
    }

@pytest.fixture
def sample_app_state():
    """
    テスト用のアプリケーション状態を返す。
    """
    return {
        "current_data": {},
        "current_file": None,
        "tree_data": {},
        "node_map": {},
        "selected_node_id": None,
        "expanded_nodes": set(),
        "drag_data": None,
        "is_modified": False,
        "is_tree_locked": False,
        "panel_expanded": True,
        "search_query": ""
    }

@pytest.fixture
def ui_controls():
    """
    テスト用のUIコントロールを返す。
    """
    page = MockPage()
    return {
        "page": page,
        "tree_view": MockControl(controls=[]),
        "detail_form": MockControl(controls=[]),
        "panel_expand_button": MockControl(),
        "tree_lock_switch": MockControl(),
        "file_picker": MagicMock(),
        "save_file_picker": MagicMock(),
        "progress_bar": MagicMock(),
        "status_text": MagicMock(),
        "toast": MagicMock(),
        "loading_indicator": MagicMock(),
        "main_content": MockContainer(controls=[]),
        "header_bar": MockAppBar(),
        "status_bar": MockContainer()
    }