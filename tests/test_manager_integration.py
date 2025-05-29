"""
Integration tests for manager components and their interactions.
"""
import os
import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

# Import managers
from src.managers.data_manager import DataManager
from src.managers.ui_manager import UIManager
from src.managers.search_manager import SearchManager
from src.managers.drag_drop_manager import DragDropManager
from src.managers.form_manager import FormManager
from src.managers.analysis_manager import AnalysisManager
from src.managers.ui_state_manager import UIStateManager

# Import event system
from src.event_hub import EventHub, EventTypes

# Import error and feedback systems for integration
from src.error_handling import ErrorHandler
from src.feedback import FeedbackManager


@pytest.fixture
def event_hub():
    """Creates an EventHub instance for testing."""
    event_hub = EventHub()
    return event_hub


@pytest.fixture
def data_manager(sample_app_state, temp_dir):
    """Creates a DataManager instance for testing."""
    sample_app_state["app_dir"] = temp_dir
    data_manager = DataManager(sample_app_state)
    return data_manager


@pytest.fixture
def ui_manager(ui_controls, sample_app_state):
    """Creates a UIManager instance for testing."""
    ui_manager = UIManager(ui_controls, sample_app_state)
    return ui_manager


@pytest.fixture
def search_manager(ui_controls, sample_app_state):
    """Creates a SearchManager instance for testing."""
    search_manager = SearchManager(ui_controls, sample_app_state)
    return search_manager


@pytest.fixture
def integrated_managers(event_hub, data_manager, ui_manager, search_manager, sample_app_state):
    """Creates an integrated setup with multiple managers connected via EventHub."""
    # Add the event hub to app state
    sample_app_state["event_hub"] = event_hub
    
    # Connect managers to event hub
    data_manager.connect_to_event_hub()
    ui_manager.connect_to_event_hub()
    search_manager.connect_to_event_hub()
    
    # Return a dictionary of all components
    return {
        "event_hub": event_hub,
        "data_manager": data_manager,
        "ui_manager": ui_manager,
        "search_manager": search_manager,
        "app_state": sample_app_state
    }


@pytest.mark.integration
class TestDataUIIntegration:
    """Tests for integration between DataManager and UIManager."""

    def test_data_load_triggers_ui_update(self, integrated_managers, temp_dir):
        """Test that loading data triggers UI tree update."""
        # Create test data
        test_file = os.path.join(temp_dir, "test_data.json")
        test_data = {"key1": "value1", "key2": {"nested": "value2"}}
        with open(test_file, "w") as f:
            json.dump(test_data, f)
        
        # Mock the UI update method to check if it's called
        with patch.object(integrated_managers["ui_manager"], 'update_tree') as mock_update_tree:
            # Load the data
            integrated_managers["data_manager"].load_json_file(test_file)
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify UI update was triggered
            mock_update_tree.assert_called_once()

    def test_ui_node_selection_updates_form(self, integrated_managers):
        """Test that selecting a node in the UI updates the form."""
        # Set up test data in the data manager
        test_data = {"key1": "value1", "key2": {"nested": "value2"}}
        integrated_managers["data_manager"].current_data = test_data
        
        # Mock the form update method
        with patch.object(integrated_managers["ui_manager"], 'update_detail_form') as mock_update_form:
            # Simulate node selection event
            integrated_managers["event_hub"].publish(
                EventTypes.NODE_SELECTED,
                {
                    "source": "ui_manager",
                    "node_path": ["key2", "nested"],
                    "node_value": "value2"
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify form update was triggered
            mock_update_form.assert_called_once()

    def test_data_update_from_form(self, integrated_managers):
        """Test that form submission updates the data."""
        # Set up test data in the data manager
        test_data = {"key1": "value1", "key2": {"nested": "value2"}}
        integrated_managers["data_manager"].current_data = test_data
        
        # Mock the set value method to check if it's called
        with patch.object(integrated_managers["data_manager"], 'set_value_by_path') as mock_set_value:
            # Simulate form submission event
            integrated_managers["event_hub"].publish(
                EventTypes.FORM_SUBMITTED,
                {
                    "source": "ui_manager",
                    "node_path": ["key2", "nested"],
                    "new_value": "updated_value",
                    "value_type": "string"
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify data update was triggered
            mock_set_value.assert_called_once_with(
                ["key2", "nested"], 
                "updated_value", 
                "string"
            )


@pytest.mark.integration
class TestSearchIntegration:
    """Tests for integration with the SearchManager."""

    def test_search_triggers_ui_highlights(self, integrated_managers):
        """Test that search results are highlighted in the UI."""
        # Set up test data
        test_data = {
            "key1": "value1",
            "key2": {"nested1": "value2", "nested2": "searchable_value"}
        }
        integrated_managers["data_manager"].current_data = test_data
        
        # Mock the highlight method
        with patch.object(integrated_managers["ui_manager"], 'highlight_search_results') as mock_highlight:
            # Simulate search event
            integrated_managers["event_hub"].publish(
                EventTypes.SEARCH_PERFORMED,
                {
                    "source": "search_manager",
                    "query": "searchable",
                    "results": [["key2", "nested2"]]
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify UI highlighting was triggered
            mock_highlight.assert_called_once()
            assert mock_highlight.call_args[0][0] == [["key2", "nested2"]]

    def test_search_with_no_results(self, integrated_managers):
        """Test search with no results found."""
        # Set up test data
        test_data = {"key1": "value1", "key2": {"nested": "value2"}}
        integrated_managers["data_manager"].current_data = test_data
        
        # Mock the feedback manager's show_toast method
        feedback_manager = MagicMock()
        integrated_managers["app_state"]["feedback_manager"] = feedback_manager
        
        # Simulate search with no results
        integrated_managers["event_hub"].publish(
            EventTypes.SEARCH_PERFORMED,
            {
                "source": "search_manager",
                "query": "nonexistent",
                "results": []
            }
        )
        
        # Let the event propagate
        time.sleep(0.1)
        
        # Verify feedback was shown
        feedback_manager.show_toast.assert_called_once()
        assert "no results" in feedback_manager.show_toast.call_args[0][0].lower()


@pytest.mark.integration
class TestErrorIntegration:
    """Tests for error handling integration across managers."""

    def test_data_error_propagation(self, integrated_managers, temp_dir):
        """Test that data errors are properly propagated and handled."""
        # Add error handler to the system
        error_handler = ErrorHandler(integrated_managers["app_state"])
        integrated_managers["app_state"]["error_handler"] = error_handler
        
        # Mock error handler's handle_error method
        with patch.object(error_handler, 'handle_error') as mock_handle_error:
            # Create an invalid JSON file
            invalid_file = os.path.join(temp_dir, "invalid.json")
            with open(invalid_file, "w") as f:
                f.write("{invalid json")
            
            # Try to load the invalid file
            try:
                integrated_managers["data_manager"].load_json_file(invalid_file)
            except:
                pass  # Expected to raise an error
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
            # Check that it's a JSON parsing error
            error = mock_handle_error.call_args[0][0]
            assert "json" in str(error).lower()

    def test_ui_error_recovery(self, integrated_managers):
        """Test UI error recovery mechanism."""
        # Add error handler and feedback manager
        error_handler = ErrorHandler(integrated_managers["app_state"])
        feedback_manager = MagicMock()
        integrated_managers["app_state"]["error_handler"] = error_handler
        integrated_managers["app_state"]["feedback_manager"] = feedback_manager
        
        # Create a test recovery action
        recovery_action = Mock()
        
        # Simulate UI error with recovery option
        with patch.object(error_handler, 'handle_error', side_effect=error_handler.handle_error) as mock_handle_error:
            # Trigger an error in UI manager with recovery action
            try:
                # Force an error in the UI manager
                integrated_managers["ui_manager"].recovery_test_error = True
                integrated_managers["ui_manager"].test_recovery_action = recovery_action
                
                # Call a method that can trigger error
                integrated_managers["ui_manager"].update_tree()
            except:
                pass  # Expected to raise an error
            
            # Verify error was handled
            mock_handle_error.assert_called_once()
            
            # Simulate user selecting recovery action
            error = mock_handle_error.call_args[0][0]
            if hasattr(error, "recovery_actions") and error.recovery_actions:
                action_name = list(error.recovery_actions.keys())[0]
                error.execute_recovery_action(action_name)
                
                # Verify recovery action was called
                recovery_action.assert_called_once()


@pytest.mark.e2e
class TestEndToEndWorkflows:
    """End-to-end tests for complete workflows involving multiple managers."""

    def test_load_search_edit_save_workflow(self, integrated_managers, temp_dir):
        """Test a complete workflow: load file, search for value, edit it, and save."""
        # Create test data
        test_file = os.path.join(temp_dir, "workflow_test.json")
        test_data = {
            "person": {
                "name": "John Doe",
                "email": "john@example.com",
                "address": {
                    "city": "New York",
                    "country": "USA"
                }
            },
            "settings": {
                "theme": "dark",
                "notifications": True
            }
        }
        with open(test_file, "w") as f:
            json.dump(test_data, f)
        
        # Add necessary components
        feedback_manager = MagicMock()
        form_manager = MagicMock()
        integrated_managers["app_state"]["feedback_manager"] = feedback_manager
        integrated_managers["app_state"]["form_manager"] = form_manager
        
        # 1. Load the file
        integrated_managers["data_manager"].load_json_file(test_file)
        
        # 2. Perform search for email
        search_results = [["person", "email"]]
        with patch.object(integrated_managers["search_manager"], 'search', return_value=search_results):
            integrated_managers["event_hub"].publish(
                EventTypes.SEARCH_REQUESTED,
                {
                    "source": "ui_manager",
                    "query": "john@example.com"
                }
            )
        
        # 3. Select the search result node
        integrated_managers["event_hub"].publish(
            EventTypes.NODE_SELECTED,
            {
                "source": "ui_manager",
                "node_path": ["person", "email"],
                "node_value": "john@example.com"
            }
        )
        
        # 4. Edit the value through form submission
        integrated_managers["event_hub"].publish(
            EventTypes.FORM_SUBMITTED,
            {
                "source": "form_manager",
                "node_path": ["person", "email"],
                "new_value": "john.doe@example.com",
                "value_type": "string"
            }
        )
        
        # 5. Save the file with new name
        output_file = os.path.join(temp_dir, "updated_workflow.json")
        integrated_managers["data_manager"].save_json_file(output_file)
        
        # 6. Verify the file was saved with updated content
        with open(output_file, "r") as f:
            saved_data = json.load(f)
        
        assert saved_data["person"]["email"] == "john.doe@example.com"

    def test_drag_drop_integration(self, integrated_managers):
        """Test drag and drop integration between managers."""
        # Set up test data
        test_data = {
            "section1": {
                "item1": "value1",
                "item2": "value2"
            },
            "section2": {}
        }
        integrated_managers["data_manager"].current_data = test_data
        
        # Create and connect drag drop manager
        drag_drop_manager = MagicMock()
        integrated_managers["app_state"]["drag_drop_manager"] = drag_drop_manager
        
        # Mock data manager's move_value_by_path method
        with patch.object(integrated_managers["data_manager"], 'move_value_by_path') as mock_move_value:
            # Simulate drag and drop event
            integrated_managers["event_hub"].publish(
                EventTypes.NODE_DRAGGED,
                {
                    "source": "ui_manager",
                    "source_path": ["section1", "item1"],
                    "target_path": ["section2"],
                    "position": "inside"
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify data manager was called to move the value
            mock_move_value.assert_called_once()
            assert mock_move_value.call_args[0][0] == ["section1", "item1"]
            assert mock_move_value.call_args[0][1] == ["section2"]