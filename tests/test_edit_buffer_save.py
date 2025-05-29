"""
Test cases for edit buffer save functionality
"""
import pytest
import flet as ft
import json
import os
from unittest.mock import Mock, MagicMock, patch
from src.managers.form_manager import FormManager
from src.managers.ui_manager import UIManager
from src.managers.data_manager import DataManager


class TestEditBufferSave:
    """Tests for ensuring edit buffer is applied before saving"""
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock Flet page"""
        page = Mock(spec=ft.Page)
        page.update = Mock()
        page.snack_bar = None
        page.overlay = []
        page.dialog = None
        return page
    
    @pytest.fixture
    def app_state(self):
        """Create test app state"""
        return {
            "data_map": {
                "item1": {
                    "id": "item1",
                    "name": "Test Item",
                    "value": 100
                }
            },
            "raw_data": [
                {
                    "id": "item1",
                    "name": "Test Item",
                    "value": 100
                }
            ],
            "id_key": "id",
            "selected_node_id": "item1",
            "edit_buffer": {},
            "is_dirty": False,
            "file_path": None,
            "current_file": None
        }
    
    @pytest.fixture
    def ui_controls(self):
        """Create mock UI controls"""
        return {
            "save_button": Mock(),
            "save_as_button": Mock(),
            "status_bar": Mock()
        }
    
    @pytest.fixture
    def form_manager(self, app_state, ui_controls):
        """Create FormManager instance"""
        return FormManager(app_state, ui_controls)
    
    @pytest.fixture
    def ui_manager(self, app_state, ui_controls, mock_page):
        """Create UIManager instance"""
        return UIManager(app_state, ui_controls, mock_page)
    
    @pytest.fixture
    def data_manager(self, app_state, ui_controls, mock_page):
        """Create DataManager instance"""
        return DataManager(app_state, ui_controls, mock_page)
    
    def test_apply_edit_buffer_to_data_with_changes(self, form_manager, app_state):
        """Test applying edit buffer with pending changes"""
        # Setup edit buffer with changes
        app_state["edit_buffer"] = {
            "name": "Updated Item",
            "value": 200
        }
        app_state["is_dirty"] = True
        
        # Apply edit buffer
        success, errors = form_manager.apply_edit_buffer_to_data()
        
        # Verify success
        assert success is True
        assert errors == {}
        
        # Verify data was updated
        assert app_state["data_map"]["item1"]["name"] == "Updated Item"
        assert app_state["data_map"]["item1"]["value"] == 200
        
        # Verify raw_data was updated
        assert app_state["raw_data"][0]["name"] == "Updated Item"
        assert app_state["raw_data"][0]["value"] == 200
        
        # Verify buffer was cleared
        assert app_state["edit_buffer"] == {}
        assert app_state["is_dirty"] is False
    
    def test_apply_edit_buffer_no_changes(self, form_manager, app_state):
        """Test applying empty edit buffer"""
        # No changes in buffer
        app_state["edit_buffer"] = {}
        
        # Apply edit buffer
        success, errors = form_manager.apply_edit_buffer_to_data()
        
        # Verify success with no changes
        assert success is True
        assert errors == {}
        
        # Verify data unchanged
        assert app_state["data_map"]["item1"]["name"] == "Test Item"
        assert app_state["data_map"]["item1"]["value"] == 100
    
    def test_apply_edit_buffer_no_node_selected(self, form_manager, app_state):
        """Test applying edit buffer with no node selected"""
        app_state["selected_node_id"] = None
        app_state["edit_buffer"] = {"name": "Updated"}
        
        # Apply edit buffer
        success, errors = form_manager.apply_edit_buffer_to_data()
        
        # Verify failure
        assert success is False
        assert "general" in errors
        assert "ノードが選択されていません" in errors["general"]
    
    def test_save_file_directly_applies_buffer(self, ui_manager, form_manager, data_manager, app_state, tmp_path):
        """Test that save_file_directly applies edit buffer before saving"""
        # Setup
        test_file = tmp_path / "test.json"
        app_state["form_manager"] = form_manager
        app_state["data_manager"] = data_manager
        app_state["edit_buffer"] = {
            "name": "Updated via Ctrl+S",
            "value": 300
        }
        app_state["is_dirty"] = True
        
        # Mock save_json_file to verify data state
        saved_data = None
        def mock_save(file_path):
            nonlocal saved_data
            saved_data = app_state["raw_data"]
            return True
        
        data_manager.save_json_file = Mock(side_effect=mock_save)
        
        # Execute save
        success = ui_manager.save_file_directly(str(test_file))
        
        # Verify success
        assert success is True
        
        # Verify edit buffer was applied before save
        assert saved_data[0]["name"] == "Updated via Ctrl+S"
        assert saved_data[0]["value"] == 300
        
        # Verify buffer was cleared
        assert app_state["edit_buffer"] == {}
        assert app_state["is_dirty"] is False
    
    def test_save_confirmation_applies_buffer(self, ui_manager, form_manager, data_manager, app_state):
        """Test that save confirmation dialog applies edit buffer"""
        # Setup
        app_state["form_manager"] = form_manager
        app_state["data_manager"] = data_manager
        app_state["edit_buffer"] = {
            "name": "Updated via dialog",
            "value": 400
        }
        app_state["node_deleted_since_last_save"] = True
        
        # Mock save_json_file
        data_manager.save_json_file = Mock(return_value=True)
        
        # Execute save through confirmation
        ui_manager._handle_save_confirmation("/path/to/file.json")
        
        # Verify data was updated before save
        assert app_state["data_map"]["item1"]["name"] == "Updated via dialog"
        assert app_state["data_map"]["item1"]["value"] == 400
        
        # Verify save was called
        data_manager.save_json_file.assert_called_once()
    
    def test_edit_buffer_with_id_change(self, form_manager, app_state):
        """Test applying edit buffer with ID change"""
        # Setup ID change
        app_state["edit_buffer"] = {
            "id": "item2",
            "name": "Renamed Item"
        }
        
        # Apply edit buffer
        success, errors = form_manager.apply_edit_buffer_to_data()
        
        # Verify success
        assert success is True
        assert errors == {}
        
        # Verify ID was changed
        assert "item1" not in app_state["data_map"]
        assert "item2" in app_state["data_map"]
        assert app_state["data_map"]["item2"]["id"] == "item2"
        assert app_state["data_map"]["item2"]["name"] == "Renamed Item"
        
        # Verify selected node was updated
        assert app_state["selected_node_id"] == "item2"
    
    def test_edit_buffer_with_duplicate_id(self, form_manager, app_state):
        """Test applying edit buffer with duplicate ID"""
        # Add another item
        app_state["data_map"]["item2"] = {"id": "item2", "name": "Existing Item"}
        
        # Try to change to existing ID
        app_state["edit_buffer"] = {
            "id": "item2"
        }
        
        # Apply edit buffer
        success, errors = form_manager.apply_edit_buffer_to_data()
        
        # Verify failure
        assert success is False
        assert "id" in errors
        assert "既に使用されています" in errors["id"]
        
        # Verify no changes were made
        assert app_state["selected_node_id"] == "item1"
        assert "item1" in app_state["data_map"]