"""
Integration tests for the FeedbackManager and its interaction with other components.
"""
import os
import time
import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the components we're testing
from src.feedback import FeedbackManager, OperationStatus
from src.event_hub import EventHub, EventTypes

# Import error handling for integration testing
from src.error_handling import ErrorHandler, AppError, ErrorCategory, ErrorSeverity


# Mark tests by categories
pytestmark = pytest.mark.feedback


@pytest.fixture
def feedback_manager(ui_controls, sample_app_state):
    """Creates a FeedbackManager instance for testing."""
    feedback_manager = FeedbackManager(ui_controls, sample_app_state)
    # Initialize the manager
    feedback_manager.initialize()
    return feedback_manager


@pytest.fixture
def event_hub():
    """Creates an EventHub instance for testing."""
    event_hub = EventHub()
    return event_hub


@pytest.fixture
def error_handler(sample_app_state):
    """Creates an ErrorHandler instance for testing integration with FeedbackManager."""
    error_handler = ErrorHandler(sample_app_state)
    return error_handler


@pytest.mark.unit
class TestFeedbackManagerUnit:
    """Unit tests for the FeedbackManager class."""

    def test_operation_registration(self, feedback_manager):
        """Test registering an operation with the FeedbackManager."""
        op_id = feedback_manager.register_operation("Test Operation")
        assert op_id is not None
        assert op_id in feedback_manager.operations
        assert feedback_manager.operations[op_id].name == "Test Operation"
        assert feedback_manager.operations[op_id].status == OperationStatus.IDLE

    def test_operation_start(self, feedback_manager):
        """Test starting an operation with the FeedbackManager."""
        op_id = feedback_manager.register_operation("Test Operation")
        feedback_manager.start_operation(op_id)
        assert feedback_manager.operations[op_id].status == OperationStatus.LOADING
        assert feedback_manager.operations[op_id].start_time is not None

    def test_operation_update(self, feedback_manager):
        """Test updating an operation's progress with the FeedbackManager."""
        op_id = feedback_manager.register_operation("Test Operation")
        feedback_manager.start_operation(op_id)
        feedback_manager.update_operation(op_id, progress=0.5, message="Halfway done")
        assert feedback_manager.operations[op_id].progress == 0.5
        assert feedback_manager.operations[op_id].message == "Halfway done"

    def test_operation_completion(self, feedback_manager):
        """Test completing an operation with the FeedbackManager."""
        op_id = feedback_manager.register_operation("Test Operation")
        feedback_manager.start_operation(op_id)
        feedback_manager.complete_operation(op_id, success=True, message="Operation completed")
        assert feedback_manager.operations[op_id].status == OperationStatus.SUCCESS
        assert feedback_manager.operations[op_id].end_time is not None
        assert feedback_manager.operations[op_id].message == "Operation completed"

    def test_operation_error(self, feedback_manager):
        """Test marking an operation as failed with the FeedbackManager."""
        op_id = feedback_manager.register_operation("Test Operation")
        feedback_manager.start_operation(op_id)
        feedback_manager.complete_operation(op_id, success=False, message="Operation failed")
        assert feedback_manager.operations[op_id].status == OperationStatus.ERROR
        assert feedback_manager.operations[op_id].end_time is not None
        assert feedback_manager.operations[op_id].message == "Operation failed"

    def test_toast_notification(self, feedback_manager):
        """Test showing toast notifications."""
        with patch.object(feedback_manager, '_update_ui') as mock_update_ui:
            feedback_manager.show_toast("Test Toast", "info")
            mock_update_ui.assert_called()
            # Verify that the toast is shown and properly configured
            assert feedback_manager.current_toast.visible
            assert feedback_manager.current_toast.bgcolor == feedback_manager.TOAST_COLORS["info"]
            assert "Test Toast" in feedback_manager.current_toast.content.value

    def test_status_indicator(self, feedback_manager):
        """Test updating the status indicator."""
        with patch.object(feedback_manager, '_update_ui') as mock_update_ui:
            feedback_manager.update_status_indicator("Working...", "loading")
            mock_update_ui.assert_called()
            # Verify that the status indicator is updated
            assert "Working..." in feedback_manager.status_indicator.content.value


@pytest.mark.integration
class TestFeedbackEventIntegration:
    """Integration tests for the FeedbackManager with the event system."""

    def test_event_feedback_subscription(self, feedback_manager, event_hub, sample_app_state):
        """Test that the FeedbackManager correctly subscribes to events."""
        # Connect the feedback manager to the event hub
        sample_app_state["event_hub"] = event_hub
        feedback_manager.connect_to_event_hub()
        
        # Mock the show_toast method to check if it's called
        with patch.object(feedback_manager, 'show_toast') as mock_show_toast:
            # Publish a data loaded event
            event_hub.publish(EventTypes.DATA_LOADED, {"source": "test", "data_size": 100})
            
            # Let the event be processed
            time.sleep(0.1)
            
            # Check if the feedback manager responded to the event
            mock_show_toast.assert_called_once()
            # The exact message will depend on implementation details
            assert "loaded" in mock_show_toast.call_args[0][0].lower()

    def test_operation_feedback_with_events(self, feedback_manager, event_hub, sample_app_state):
        """Test operation feedback in response to events."""
        # Connect the feedback manager to the event hub
        sample_app_state["event_hub"] = event_hub
        feedback_manager.connect_to_event_hub()
        
        # Mock the methods used for operation tracking
        with patch.object(feedback_manager, 'register_operation', return_value="test-op") as mock_register, \
             patch.object(feedback_manager, 'start_operation') as mock_start, \
             patch.object(feedback_manager, 'complete_operation') as mock_complete:
            
            # Publish operation start event
            event_hub.publish(EventTypes.OPERATION_STARTED, {
                "source": "data_manager", 
                "operation": "load_file",
                "details": {"file_path": "test.json"}
            })
            
            # Let the event be processed
            time.sleep(0.1)
            
            # Check if the operation was registered and started
            mock_register.assert_called_once()
            mock_start.assert_called_once()
            
            # Publish operation complete event
            event_hub.publish(EventTypes.OPERATION_COMPLETED, {
                "source": "data_manager", 
                "operation": "load_file",
                "success": True,
                "details": {"file_path": "test.json"}
            })
            
            # Let the event be processed
            time.sleep(0.1)
            
            # Check if the operation was completed
            mock_complete.assert_called_once()
            assert mock_complete.call_args[1]["success"] is True

    def test_error_event_feedback(self, feedback_manager, event_hub, sample_app_state):
        """Test feedback response to error events."""
        # Connect the feedback manager to the event hub
        sample_app_state["event_hub"] = event_hub
        feedback_manager.connect_to_event_hub()
        
        # Mock the show_toast method to check if it's called
        with patch.object(feedback_manager, 'show_toast') as mock_show_toast:
            # Publish an error event
            event_hub.publish(EventTypes.ERROR_OCCURRED, {
                "source": "data_manager",
                "error": {
                    "message": "Failed to parse JSON",
                    "severity": ErrorSeverity.ERROR,
                    "category": ErrorCategory.DATA_ERROR
                }
            })
            
            # Let the event be processed
            time.sleep(0.1)
            
            # Check if the feedback manager showed an error toast
            mock_show_toast.assert_called_once()
            # The exact message will depend on implementation details
            assert mock_show_toast.call_args[1]["toast_type"] == "error"


@pytest.mark.integration
class TestFeedbackErrorHandlerIntegration:
    """Integration tests for the FeedbackManager with the ErrorHandler."""

    def test_error_handler_feedback_integration(self, feedback_manager, error_handler, sample_app_state):
        """Test that the FeedbackManager responds to errors from the ErrorHandler."""
        # Connect both managers
        sample_app_state["feedback_manager"] = feedback_manager
        
        # Mock the show_toast method to check if it's called
        with patch.object(feedback_manager, 'show_toast') as mock_show_toast:
            # Create and handle an error
            error = AppError(
                message="Test error",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.DATA_ERROR
            )
            error_handler.handle_error(error)
            
            # Check if the feedback manager showed an error toast
            mock_show_toast.assert_called_once()
            assert "Test error" in mock_show_toast.call_args[0][0]
            assert mock_show_toast.call_args[1]["toast_type"] == "error"

    def test_recovery_action_feedback(self, feedback_manager, error_handler, sample_app_state):
        """Test that the FeedbackManager shows recovery action feedback."""
        # Connect both managers
        sample_app_state["feedback_manager"] = feedback_manager
        
        # Mock the show_toast method to check if it's called
        with patch.object(feedback_manager, 'show_toast') as mock_show_toast:
            # Create an error with recovery actions
            error = AppError(
                message="Test error with recovery",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.DATA_ERROR
            )
            # Add recovery actions
            error.add_recovery_action("retry", "Retry operation", lambda: None)
            error.add_recovery_action("ignore", "Ignore error", lambda: None)
            
            # Handle the error
            error_handler.handle_error(error)
            
            # Check if recovery options were shown in the feedback
            mock_show_toast.assert_called()
            toast_call = mock_show_toast.call_args[0][0]
            assert "recovery" in toast_call.lower() or "action" in toast_call.lower()


@pytest.mark.e2e
class TestFeedbackE2EScenarios:
    """End-to-end scenarios testing the FeedbackManager in realistic workflows."""

    def test_file_operation_feedback_flow(self, feedback_manager, sample_app_state, temp_dir):
        """Test a complete file operation workflow with user feedback."""
        # Create a mock data manager
        data_manager = MagicMock()
        sample_app_state["data_manager"] = data_manager
        sample_app_state["feedback_manager"] = feedback_manager
        
        # Create a test file path
        test_file = os.path.join(temp_dir, "test.json")
        
        # Mock file operations with the with_feedback decorator integrated
        with patch('fledjson.feedback.with_feedback', side_effect=lambda x, y: lambda func: func):
            # Mock successful file load
            with patch.object(feedback_manager, 'register_operation', return_value="load-op") as mock_register, \
                 patch.object(feedback_manager, 'start_operation') as mock_start, \
                 patch.object(feedback_manager, 'update_operation') as mock_update, \
                 patch.object(feedback_manager, 'complete_operation') as mock_complete, \
                 patch.object(feedback_manager, 'show_toast') as mock_toast:
                
                # Simulate file load operation
                data_manager.load_json_file.return_value = {"test": "data"}
                data_manager.load_json_file(test_file)
                
                # Verify feedback flow for file load
                mock_register.assert_called_once()
                mock_start.assert_called_once()
                mock_complete.assert_called_once()
                assert mock_complete.call_args[1]["success"] is True
                mock_toast.assert_called()

    def test_long_operation_progress_feedback(self, feedback_manager, sample_app_state):
        """Test feedback for a long-running operation with progress updates."""
        # Register and start a long operation
        op_id = feedback_manager.register_operation("Long Process")
        feedback_manager.start_operation(op_id)
        
        # Mock the UI update method
        with patch.object(feedback_manager, '_update_ui') as mock_update_ui:
            # Simulate progress updates
            for progress in [0.25, 0.5, 0.75, 1.0]:
                feedback_manager.update_operation(
                    op_id, 
                    progress=progress, 
                    message=f"Processing: {int(progress * 100)}%"
                )
                # In a real scenario, we'd have some processing here
                time.sleep(0.01)
            
            # Complete the operation
            feedback_manager.complete_operation(op_id, success=True, message="Process completed")
            
            # Verify UI was updated for the progress steps
            assert mock_update_ui.call_count >= 5  # 4 updates + completion
            
            # Verify final operation state
            assert feedback_manager.operations[op_id].status == OperationStatus.SUCCESS
            assert feedback_manager.operations[op_id].progress == 1.0

    def test_cancellable_operation_feedback(self, feedback_manager, sample_app_state):
        """Test feedback for a cancellable operation."""
        # Create a cancellation callback
        cancel_callback = Mock()
        
        # Register a cancellable operation
        op_id = feedback_manager.register_operation(
            "Cancellable Operation", 
            cancellable=True,
            cancel_callback=cancel_callback
        )
        feedback_manager.start_operation(op_id)
        
        # Verify the operation is cancellable
        assert feedback_manager.operations[op_id].cancellable
        assert feedback_manager.operations[op_id].cancel_callback == cancel_callback
        
        # Mock UI update
        with patch.object(feedback_manager, '_update_ui'):
            # Test cancellation
            feedback_manager.cancel_operation(op_id)
            
            # Verify cancellation callback was called
            cancel_callback.assert_called_once()
            
            # Verify operation state
            assert feedback_manager.operations[op_id].status == OperationStatus.CANCELLED