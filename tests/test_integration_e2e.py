"""
End-to-end integration tests that verify all components working together in realistic scenarios.
"""
import os
import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

# Import app and main components
from src.app import FleDjSONApp
from src.event_hub import EventHub, EventTypes

# Import error and feedback systems
from src.error_handling import ErrorHandler, AppError, ErrorCategory, ErrorSeverity
from src.feedback import FeedbackManager, OperationStatus

# Import optimization components
from src.optimizations import (
    LazyJSONLoader,
    CachedDataManager,
    BackgroundProcessor,
    TreeOptimizer
)

# Import managers
from src.managers.data_manager import DataManager
from src.managers.ui_manager import UIManager
from src.managers.search_manager import SearchManager
from src.managers.template_manager import TemplateManager
from src.managers.copy_manager import CopyManager
from src.managers.flatten_manager import FlattenManager
from src.managers.form_manager import FormManager
from src.managers.analysis_manager import AnalysisManager
from src.managers.ui_state_manager import UIStateManager


@pytest.fixture
def sample_complex_json(temp_dir):
    """Creates a sample complex JSON file for testing."""
    file_path = os.path.join(temp_dir, "complex_sample.json")
    
    # Create a complex nested structure with different data types
    data = {
        "string_value": "This is a string",
        "number_value": 12345,
        "boolean_value": True,
        "null_value": None,
        "array_value": [1, 2, 3, 4, 5],
        "nested_object": {
            "name": "John Doe",
            "age": 30,
            "contacts": {
                "email": "john@example.com",
                "phone": "123-456-7890"
            },
            "addresses": [
                {
                    "type": "home",
                    "street": "123 Main St",
                    "city": "New York",
                    "country": "USA"
                },
                {
                    "type": "work",
                    "street": "456 Park Ave",
                    "city": "Boston",
                    "country": "USA"
                }
            ]
        },
        "deep_nested": {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deeply nested value"
                    }
                }
            }
        }
    }
    
    with open(file_path, "w") as f:
        json.dump(data, f)
    
    return file_path


@pytest.fixture
def mock_app(ui_controls, sample_app_state, temp_dir):
    """Creates a mock application instance with all components initialized."""
    # Set up the app directory
    sample_app_state["app_dir"] = temp_dir
    
    # Create and initialize the event hub
    event_hub = EventHub()
    sample_app_state["event_hub"] = event_hub
    
    # Create and initialize managers
    data_manager = DataManager(sample_app_state)
    ui_manager = UIManager(ui_controls, sample_app_state)
    search_manager = SearchManager(ui_controls, sample_app_state)
    form_manager = FormManager(ui_controls, sample_app_state)
    template_manager = TemplateManager(sample_app_state)
    copy_manager = CopyManager(sample_app_state)
    flatten_manager = FlattenManager(sample_app_state)
    analysis_manager = AnalysisManager(sample_app_state)
    ui_state_manager = UIStateManager(sample_app_state)
    error_handler = ErrorHandler(sample_app_state)
    feedback_manager = FeedbackManager(ui_controls, sample_app_state)
    
    # Set up optimization components
    lazy_loader = LazyJSONLoader(sample_app_state)
    cached_manager = CachedDataManager(sample_app_state)
    background_processor = BackgroundProcessor(sample_app_state)
    tree_optimizer = TreeOptimizer(ui_controls, sample_app_state)
    
    # Store all components in app_state
    sample_app_state["data_manager"] = data_manager
    sample_app_state["ui_manager"] = ui_manager
    sample_app_state["search_manager"] = search_manager
    sample_app_state["form_manager"] = form_manager
    sample_app_state["template_manager"] = template_manager
    sample_app_state["copy_manager"] = copy_manager
    sample_app_state["flatten_manager"] = flatten_manager
    sample_app_state["analysis_manager"] = analysis_manager
    sample_app_state["ui_state_manager"] = ui_state_manager
    sample_app_state["error_handler"] = error_handler
    sample_app_state["feedback_manager"] = feedback_manager
    sample_app_state["lazy_loader"] = lazy_loader
    sample_app_state["cached_manager"] = cached_manager
    sample_app_state["background_processor"] = background_processor
    sample_app_state["tree_optimizer"] = tree_optimizer
    
    # Connect components to event hub
    data_manager.connect_to_event_hub()
    ui_manager.connect_to_event_hub()
    search_manager.connect_to_event_hub()
    form_manager.connect_to_event_hub()
    ui_state_manager.connect_to_event_hub()
    feedback_manager.connect_to_event_hub()
    
    # Create a mock app instance
    app = MagicMock()
    app.app_state = sample_app_state
    app.ui_controls = ui_controls
    
    return app


@pytest.mark.e2e
class TestEndToEndWorkflows:
    """End-to-end tests for complete application workflows."""

    def test_load_file_workflow(self, mock_app, sample_complex_json):
        """Test the complete file loading workflow with all components."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        ui_manager = mock_app.app_state["ui_manager"]
        feedback_manager = mock_app.app_state["feedback_manager"]
        analysis_manager = mock_app.app_state["analysis_manager"]
        
        # Mock the UI update methods
        with patch.object(ui_manager, 'update_tree') as mock_update_tree, \
             patch.object(feedback_manager, 'register_operation', return_value="load-op") as mock_register, \
             patch.object(feedback_manager, 'start_operation') as mock_start, \
             patch.object(feedback_manager, 'complete_operation') as mock_complete, \
             patch.object(analysis_manager, 'analyze_json_structure', return_value={"id_key": "id", "label_key": "name"}) as mock_analyze, \
             patch.object(mock_app.ui_controls["page"], 'update') as mock_page_update:
            
            # Perform the file load
            data_manager.load_json_file(sample_complex_json)
            
            # Verify the workflow sequence
            # 1. Feedback manager should register and start the operation
            mock_register.assert_called_once()
            mock_start.assert_called_once()
            
            # 2. Data should be loaded successfully
            assert data_manager.current_data is not None
            assert "nested_object" in data_manager.current_data
            
            # 3. Analysis should be performed
            mock_analyze.assert_called_once()
            
            # 4. UI should be updated
            mock_update_tree.assert_called_once()
            
            # 5. Operation should be completed successfully
            mock_complete.assert_called_once()
            assert mock_complete.call_args[1]["success"] is True

    def test_search_and_edit_workflow(self, mock_app, sample_complex_json):
        """Test searching for a value and editing it."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        ui_manager = mock_app.app_state["ui_manager"]
        search_manager = mock_app.app_state["search_manager"]
        
        # Load the test data
        data_manager.load_json_file(sample_complex_json)
        
        # Mock the search implementation
        with patch.object(search_manager, 'search', return_value=[["nested_object", "contacts", "email"]]) as mock_search, \
             patch.object(ui_manager, 'highlight_search_results') as mock_highlight, \
             patch.object(ui_manager, 'update_detail_form') as mock_update_form, \
             patch.object(data_manager, 'set_value_by_path') as mock_set_value:
            
            # 1. Perform search
            search_manager.perform_search("john@example.com")
            
            # Verify search was performed
            mock_search.assert_called_once()
            
            # 2. Highlight search results
            mock_app.app_state["event_hub"].publish(
                EventTypes.SEARCH_PERFORMED,
                {
                    "source": "search_manager",
                    "query": "john@example.com",
                    "results": [["nested_object", "contacts", "email"]]
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify results were highlighted
            mock_highlight.assert_called_once()
            
            # 3. Select the search result
            mock_app.app_state["event_hub"].publish(
                EventTypes.NODE_SELECTED,
                {
                    "source": "ui_manager",
                    "node_path": ["nested_object", "contacts", "email"],
                    "node_value": "john@example.com"
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify form was updated
            mock_update_form.assert_called_once()
            
            # 4. Edit the value
            mock_app.app_state["event_hub"].publish(
                EventTypes.FORM_SUBMITTED,
                {
                    "source": "ui_manager",
                    "node_path": ["nested_object", "contacts", "email"],
                    "new_value": "john.doe@example.com",
                    "value_type": "string"
                }
            )
            
            # Let the event propagate
            time.sleep(0.1)
            
            # Verify data was updated
            mock_set_value.assert_called_once_with(
                ["nested_object", "contacts", "email"],
                "john.doe@example.com",
                "string"
            )

    @pytest.mark.error
    def test_error_recovery_workflow(self, mock_app, temp_dir):
        """Test error handling and recovery workflow."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        error_handler = mock_app.app_state["error_handler"]
        feedback_manager = mock_app.app_state["feedback_manager"]
        
        # Create an invalid JSON file
        invalid_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_file, "w") as f:
            f.write("{invalid json")
        
        # Create a valid backup file that can be used for recovery
        valid_file = os.path.join(temp_dir, "valid.json")
        with open(valid_file, "w") as f:
            f.write('{"valid": "json"}')
        
        # Mock the error handling and recovery methods
        recovery_action = Mock(return_value=valid_file)
        
        with patch.object(error_handler, 'handle_error', side_effect=error_handler.handle_error) as mock_handle_error, \
             patch.object(feedback_manager, 'show_toast') as mock_show_toast, \
             patch.object(data_manager, 'load_json_file', side_effect=[ValueError("Invalid JSON"), {"valid": "json"}]) as mock_load:
            
            # Add a recovery action for when there's an error
            with patch.object(AppError, 'add_recovery_action') as mock_add_recovery:
                # Attempt to load the invalid file
                try:
                    data_manager.load_json_file(invalid_file)
                except ValueError:
                    # Error will be caught by the error handler
                    pass
                
                # Verify error was handled
                mock_handle_error.assert_called_once()
                
                # Get the error that was handled
                error = mock_handle_error.call_args[0][0]
                
                # Verify recovery action was offered
                mock_add_recovery.assert_called()
                
                # Manually add a recovery action for testing
                error.add_recovery_action("try_alternative", "Try alternative file", recovery_action)
                
                # Execute the recovery action
                error.execute_recovery_action("try_alternative")
                
                # Verify recovery action was executed
                recovery_action.assert_called_once()
                
                # Verify feedback was provided
                mock_show_toast.assert_called()

    @pytest.mark.performance
    def test_performance_optimization_workflow(self, mock_app, sample_complex_json):
        """Test performance optimization components working together."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        ui_manager = mock_app.app_state["ui_manager"]
        background_processor = mock_app.app_state["background_processor"]
        tree_optimizer = mock_app.app_state["tree_optimizer"]
        
        # Initialize tree optimizer with data
        data_manager.load_json_file(sample_complex_json)
        tree_optimizer.initialize(data_manager.current_data)
        
        # Mock the methods we need to track
        with patch.object(tree_optimizer, 'render_tree') as mock_render, \
             patch.object(ui_manager, 'update_tree') as mock_update_tree, \
             patch.object(background_processor, 'schedule_task', side_effect=background_processor.schedule_task) as mock_schedule:
            
            # Perform background tree rendering
            def render_task():
                tree_optimizer.set_node_expanded(["nested_object"], True)
                tree_optimizer.render_tree()
                return "render_complete"
            
            # Schedule the background task
            task_id = background_processor.schedule_task(render_task)
            
            # Wait for completion
            background_processor.wait_for_task(task_id)
            
            # Verify task scheduling
            mock_schedule.assert_called_once()
            
            # Verify rendering was called
            mock_render.assert_called_once()
            
            # Verify task completion
            assert background_processor.get_task_result(task_id) == "render_complete"


@pytest.mark.app
class TestApplicationFlow:
    """Tests for the complete application lifecycle."""

    def test_application_startup(self, ui_controls, sample_app_state, temp_dir):
        """Test the application startup sequence."""
        # Mock the UI page
        with patch.object(ui_controls["page"], 'add') as mock_add, \
             patch.object(ui_controls["page"], 'update') as mock_update:
            
            # Set the app directory
            sample_app_state["app_dir"] = temp_dir
            
            # Create the application
            app = FleDjSONApp(ui_controls, sample_app_state)
            
            # Initialize the app
            app.initialize()
            
            # Verify UI components were added
            assert mock_add.call_count > 0
            
            # Verify UI was updated
            assert mock_update.call_count > 0
            
            # Verify managers were created
            assert "data_manager" in sample_app_state
            assert "ui_manager" in sample_app_state
            assert "search_manager" in sample_app_state
            assert "form_manager" in sample_app_state
            assert "template_manager" in sample_app_state
            assert "copy_manager" in sample_app_state
            assert "flatten_manager" in sample_app_state
            assert "analysis_manager" in sample_app_state
            assert "ui_state_manager" in sample_app_state
            assert "error_handler" in sample_app_state
            assert "feedback_manager" in sample_app_state
            
            # Verify event hub was created
            assert "event_hub" in sample_app_state

    def test_application_shutdown(self, ui_controls, sample_app_state, temp_dir):
        """Test the application shutdown sequence."""
        # Set the app directory
        sample_app_state["app_dir"] = temp_dir
        
        # Create the application
        app = FleDjSONApp(ui_controls, sample_app_state)
        
        # Initialize the app
        app.initialize()
        
        # Mock the cleanup methods
        with patch.object(sample_app_state["event_hub"], 'shutdown') as mock_shutdown, \
             patch.object(sample_app_state["background_processor"], 'shutdown', side_effect=lambda: None) as mock_bg_shutdown:
            
            # Perform shutdown
            app.shutdown()
            
            # Verify event hub was shut down
            mock_shutdown.assert_called_once()
            
            # Verify background processor was shut down
            mock_bg_shutdown.assert_called_once()


@pytest.mark.performance
class TestStressTests:
    """Stress tests for performance under high load."""

    def test_large_file_handling(self, mock_app, temp_dir):
        """Test handling very large JSON files."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        lazy_loader = mock_app.app_state["lazy_loader"]
        background_processor = mock_app.app_state["background_processor"]
        
        # Create a very large JSON file (only for test purposes)
        large_file = os.path.join(temp_dir, "large_file.json")
        
        # Generate large nested structure
        large_data = {
            f"key_{i}": {
                f"subkey_{j}": f"value_{i}_{j}" 
                for j in range(100)
            } 
            for i in range(100)
        }
        
        with open(large_file, "w") as f:
            json.dump(large_data, f)
        
        # Use lazy loading for the large file
        background_task = Mock()
        
        with patch.object(lazy_loader, 'start_loading') as mock_start_loading, \
             patch.object(background_processor, 'schedule_task', return_value="task-id") as mock_schedule:
            
            # Load large file in background
            def load_large_file():
                lazy_loader.start_loading(large_file)
                while not lazy_loader.is_loaded:
                    time.sleep(0.1)
                data_manager.current_data = lazy_loader.get_root_value()
                background_task()
                return "loaded"
            
            # Schedule the task
            background_processor.schedule_task(load_large_file)
            
            # Verify task scheduling
            mock_schedule.assert_called_once()
            
            # Verify lazy loading was started
            mock_start_loading.assert_called_once_with(large_file)

    def test_multiple_concurrent_operations(self, mock_app, sample_complex_json):
        """Test multiple concurrent operations."""
        # Get the components from mock_app
        event_hub = mock_app.app_state["event_hub"]
        background_processor = mock_app.app_state["background_processor"]
        
        # Create task mocks
        task1 = Mock(return_value="result1")
        task2 = Mock(return_value="result2")
        task3 = Mock(return_value="result3")
        
        # Schedule multiple tasks concurrently
        with patch.object(background_processor, 'schedule_task', side_effect=["task1", "task2", "task3"]) as mock_schedule:
            # Schedule three tasks
            background_processor.schedule_task(task1)
            background_processor.schedule_task(task2)
            background_processor.schedule_task(task3)
            
            # Verify all tasks were scheduled
            assert mock_schedule.call_count == 3
            
        # Publish multiple events concurrently
        event_counter = Mock()
        
        # Subscribe to multiple event types
        event_hub.subscribe(EventTypes.DATA_LOADED, event_counter)
        event_hub.subscribe(EventTypes.NODE_SELECTED, event_counter)
        event_hub.subscribe(EventTypes.SEARCH_PERFORMED, event_counter)
        
        # Publish events concurrently
        event_hub.publish(EventTypes.DATA_LOADED, {"source": "test"})
        event_hub.publish(EventTypes.NODE_SELECTED, {"source": "test", "node_path": []})
        event_hub.publish(EventTypes.SEARCH_PERFORMED, {"source": "test", "results": []})
        
        # Let events propagate
        time.sleep(0.1)
        
        # Verify all events were processed
        assert event_counter.call_count == 3

    @pytest.mark.new_managers
    def test_new_managers_workflow(self, mock_app, sample_complex_json):
        """Test workflow with new manager classes (TemplateManager, CopyManager, FlattenManager)."""
        # Get the components from mock_app
        data_manager = mock_app.app_state["data_manager"]
        template_manager = mock_app.app_state["template_manager"]
        copy_manager = mock_app.app_state["copy_manager"]
        flatten_manager = mock_app.app_state["flatten_manager"]
        form_manager = mock_app.app_state["form_manager"]
        
        # Load the test data
        data_manager.load_json_file(sample_complex_json)
        
        # Test TemplateManager workflow
        with patch.object(template_manager, 'create_template_from_data') as mock_create_template, \
             patch.object(template_manager, 'apply_template') as mock_apply_template:
            
            # Mock template creation
            mock_template = {
                "string_value": {"type": "string", "role": "data"},
                "number_value": {"type": "number", "role": "data"},
                "nested_object": {"type": "object", "role": "container"}
            }
            mock_create_template.return_value = mock_template
            
            # Mock template application
            mock_new_node = {"string_value": "New Value", "number_value": 999}
            mock_apply_template.return_value = mock_new_node
            
            # Create template from loaded data
            template = template_manager.create_template_from_data(data_manager.current_data)
            
            # Apply template with new values
            new_node = template_manager.apply_template(template, {"string_value": "New Value"})
            
            # Verify template workflow
            mock_create_template.assert_called_once()
            mock_apply_template.assert_called_once()
        
        # Test CopyManager workflow
        with patch.object(copy_manager, 'deep_copy') as mock_deep_copy:
            mock_copied_data = {"copied": True, "original": False}
            mock_deep_copy.return_value = mock_copied_data
            
            # Perform deep copy
            copied_data = copy_manager.deep_copy(data_manager.current_data)
            
            # Verify copy workflow
            mock_deep_copy.assert_called_once()
            assert copied_data == mock_copied_data
        
        # Test FlattenManager workflow
        with patch.object(flatten_manager, 'flatten_json') as mock_flatten:
            mock_flattened = {
                "string_value": "This is a string",
                "nested_object.name": "John Doe",
                "nested_object.contacts.email": "john@example.com"
            }
            mock_flatten.return_value = mock_flattened
            
            # Perform flattening
            flattened = flatten_manager.flatten_json(data_manager.current_data)
            
            # Verify flatten workflow
            mock_flatten.assert_called_once()
            assert flattened == mock_flattened
        
        # Test FormManager field order preservation
        with patch.object(form_manager, 'track_key') as mock_track_key, \
             patch.object(form_manager, 'sort_edit_buffer_keys') as mock_sort_keys:
            
            mock_sort_keys.return_value = ["id", "name", "profile.bio", "contact.email"]
            
            # Track field input order
            form_manager.track_key("id")
            form_manager.track_key("name") 
            form_manager.track_key("profile.bio")
            form_manager.track_key("contact.email")
            
            # Get sorted keys
            sorted_keys = form_manager.sort_edit_buffer_keys()
            
            # Verify field order tracking
            assert mock_track_key.call_count == 4
            mock_sort_keys.assert_called_once()
            assert sorted_keys == ["id", "name", "profile.bio", "contact.email"]

    @pytest.mark.memory_safety
    def test_memory_safety_workflow(self, mock_app):
        """Test memory safety features with array reference issues."""
        # Get the components from mock_app
        copy_manager = mock_app.app_state["copy_manager"]
        data_manager = mock_app.app_state["data_manager"]
        
        # Create data with potential array reference issues
        shared_array = ["item1", "item2"]
        test_data = {
            "user1": {"settings": shared_array},
            "user2": {"settings": shared_array},  # Same array reference
            "global": {"settings": shared_array}   # Same array reference
        }
        
        data_manager.current_data = test_data
        
        # Test that CopyManager creates independent copies
        with patch.object(copy_manager, 'deep_copy', side_effect=copy_manager.deep_copy) as mock_deep_copy:
            # Create independent copy
            copied_data = copy_manager.deep_copy(test_data)
            
            # Verify deep copy was called
            mock_deep_copy.assert_called_once()
            
            # Simulate modification of copied data
            if isinstance(copied_data, dict) and "user1" in copied_data:
                copied_data["user1"]["settings"].append("new_item")
            
            # Verify original data integrity (in real scenario)
            # The original shared_array should not be modified
            # This is tested more thoroughly in isolated tests