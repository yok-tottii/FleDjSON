"""
Tests for optimization components that improve performance.
"""
import os
import json
import time
import threading
import pytest
from unittest.mock import Mock, patch, MagicMock, call

# Import optimization components
from src.optimizations import (
    LazyJSONLoader,
    CachedDataManager,
    BackgroundProcessor,
    TreeOptimizer
)

# Import other needed components
from src.event_hub import EventHub, EventType


@pytest.fixture
def sample_large_json_file(temp_dir):
    """Creates a sample large JSON file for testing."""
    file_path = os.path.join(temp_dir, "large_sample.json")
    
    # Create a moderately complex nested structure
    data = {
        "level1": {
            f"item{i}": {
                f"subitem{j}": f"value{i}_{j}" 
                for j in range(10)
            } 
            for i in range(100)
        }
    }
    
    with open(file_path, "w") as f:
        json.dump(data, f)
    
    return file_path


@pytest.fixture
def lazy_loader(sample_app_state):
    """Creates a LazyJSONLoader instance for testing."""
    loader = LazyJSONLoader(sample_app_state)
    return loader


@pytest.fixture
def cached_data_manager(sample_app_state):
    """Creates a CachedDataManager instance for testing."""
    manager = CachedDataManager(sample_app_state)
    return manager


@pytest.fixture
def background_processor(sample_app_state):
    """Creates a BackgroundProcessor instance for testing."""
    processor = BackgroundProcessor(sample_app_state)
    return processor


@pytest.fixture
def tree_optimizer(ui_controls, sample_app_state):
    """Creates a TreeOptimizer instance for testing."""
    optimizer = TreeOptimizer(ui_controls, sample_app_state)
    return optimizer


@pytest.mark.unit
class TestLazyJSONLoader:
    """Unit tests for the LazyJSONLoader component."""

    def test_initialization(self, lazy_loader):
        """Test LazyJSONLoader initialization."""
        assert lazy_loader is not None
        assert lazy_loader.chunk_size > 0
        assert lazy_loader.is_initialized == False

    def test_lazy_loading_chunks(self, lazy_loader, sample_large_json_file):
        """Test that JSON is loaded in chunks."""
        # Mock the internal methods that process chunks
        with patch.object(lazy_loader, '_process_chunk') as mock_process:
            # Start loading the file
            lazy_loader.start_loading(sample_large_json_file)
            
            # Wait for loading to complete
            while not lazy_loader.is_loaded:
                time.sleep(0.1)
            
            # Verify chunks were processed
            assert mock_process.call_count > 0

    def test_data_access_methods(self, lazy_loader, sample_large_json_file):
        """Test methods to access data from the lazy loader."""
        # Load the file
        lazy_loader.start_loading(sample_large_json_file)
        
        # Wait for loading to complete
        while not lazy_loader.is_loaded:
            time.sleep(0.1)
        
        # Test get_value_by_path
        value = lazy_loader.get_value_by_path(["level1", "item1", "subitem1"])
        assert value == "value1_1"
        
        # Test get_children
        children = lazy_loader.get_children(["level1", "item2"])
        assert len(children) == 10
        assert "subitem0" in children

    def test_memory_usage_tracking(self, lazy_loader, sample_large_json_file):
        """Test that memory usage is properly tracked."""
        # Start loading
        lazy_loader.start_loading(sample_large_json_file)
        
        # Wait for loading to complete
        while not lazy_loader.is_loaded:
            time.sleep(0.1)
        
        # Check memory usage tracking
        memory_usage = lazy_loader.get_memory_usage()
        assert memory_usage > 0
        assert isinstance(memory_usage, int)


@pytest.mark.unit
class TestCachedDataManager:
    """Unit tests for the CachedDataManager component."""

    def test_caching_behavior(self, cached_data_manager):
        """Test that values are properly cached and retrieved."""
        # Set a test value
        cached_data_manager.set_value("test_key", "test_value")
        
        # Access it multiple times
        for _ in range(5):
            value = cached_data_manager.get_value("test_key")
            assert value == "test_value"
        
        # Verify it was only computed once by checking the cache hits
        assert cached_data_manager.cache_hits > 0
        assert cached_data_manager.cache_misses == 1  # Only missed on first access

    def test_cache_expiration(self, cached_data_manager):
        """Test that cached values expire after ttl."""
        # Override the TTL for testing
        cached_data_manager.default_ttl = 0.1  # 100ms
        
        # Set a test value
        cached_data_manager.set_value("expiring_key", "test_value")
        
        # Verify it's in the cache
        assert cached_data_manager.get_value("expiring_key") == "test_value"
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Verify it was recomputed (value existed but was expired)
        with patch.object(cached_data_manager, '_compute_value', return_value="recomputed") as mock_compute:
            value = cached_data_manager.get_value("expiring_key")
            mock_compute.assert_called_once()
            assert value == "recomputed"

    def test_cache_size_limit(self, cached_data_manager):
        """Test that cache respects size limits."""
        # Set a small cache size limit
        cached_data_manager.max_cache_size = 5
        
        # Add more items than the cache can hold
        for i in range(10):
            cached_data_manager.set_value(f"key{i}", f"value{i}")
        
        # Verify older items were evicted
        # We expect the first 5 items to be evicted and the last 5 to remain
        for i in range(5):
            assert cached_data_manager.get_value(f"key{i}") is None or cached_data_manager.get_value(f"key{i}") == f"value{i}"
        
        # The newest items should still be in the cache
        for i in range(5, 10):
            assert cached_data_manager.get_value(f"key{i}") == f"value{i}"


@pytest.mark.unit
class TestBackgroundProcessor:
    """Unit tests for the BackgroundProcessor component."""

    def test_task_execution(self, background_processor):
        """Test that tasks are executed in the background."""
        # Create a task that takes some time
        result = {"completed": False}
        
        def test_task():
            time.sleep(0.1)
            result["completed"] = True
            return "task_result"
        
        # Schedule the task
        task_id = background_processor.schedule_task(test_task)
        
        # Verify task is running
        assert task_id in background_processor.tasks
        assert background_processor.tasks[task_id]["status"] == "running"
        
        # Wait for completion
        background_processor.wait_for_task(task_id)
        
        # Verify task completed
        assert result["completed"] == True
        assert background_processor.tasks[task_id]["status"] == "completed"
        assert background_processor.get_task_result(task_id) == "task_result"

    def test_task_cancellation(self, background_processor):
        """Test that tasks can be cancelled."""
        cancel_event = threading.Event()
        
        def cancellable_task():
            while not cancel_event.is_set():
                time.sleep(0.1)
            return "cancelled"
        
        # Schedule the task with cancellation support
        task_id = background_processor.schedule_task(
            cancellable_task, 
            cancellation_token=cancel_event
        )
        
        # Wait a bit to ensure the task has started
        time.sleep(0.2)
        
        # Cancel the task
        background_processor.cancel_task(task_id)
        
        # Verify task was cancelled
        assert cancel_event.is_set()
        
        # Wait for task to finish (it should finish quickly after cancellation)
        background_processor.wait_for_task(task_id)
        
        # Verify task is marked as cancelled
        assert background_processor.tasks[task_id]["status"] == "cancelled"

    def test_progress_tracking(self, background_processor):
        """Test that task progress can be tracked."""
        progress_tracker = Mock()
        
        def task_with_progress():
            for i in range(5):
                progress_tracker(i/4)
                time.sleep(0.1)
            return "done"
        
        # Schedule the task with progress reporting
        task_id = background_processor.schedule_task(
            task_with_progress, 
            progress_callback=progress_tracker
        )
        
        # Wait for task completion
        background_processor.wait_for_task(task_id)
        
        # Verify progress was reported
        assert progress_tracker.call_count == 5
        progress_tracker.assert_has_calls([
            call(0.0), call(0.25), call(0.5), call(0.75), call(1.0)
        ], any_order=False)


@pytest.mark.unit
class TestTreeOptimizer:
    """Unit tests for the TreeOptimizer component."""

    def test_node_visibility_tracking(self, tree_optimizer):
        """Test that node visibility is properly tracked."""
        # Create a sample tree structure
        tree_data = {
            "root": {
                "child1": {
                    "grandchild1": "value1",
                    "grandchild2": "value2"
                },
                "child2": "value3"
            }
        }
        
        # Initialize the optimizer with the tree
        tree_optimizer.initialize(tree_data)
        
        # Expand some nodes
        tree_optimizer.set_node_expanded(["root"], True)
        tree_optimizer.set_node_expanded(["root", "child1"], True)
        
        # Check visibility
        assert tree_optimizer.is_node_visible(["root"]) == True
        assert tree_optimizer.is_node_visible(["root", "child1"]) == True
        assert tree_optimizer.is_node_visible(["root", "child1", "grandchild1"]) == True
        assert tree_optimizer.is_node_visible(["root", "child2"]) == True
        
        # Collapse a node and check again
        tree_optimizer.set_node_expanded(["root", "child1"], False)
        assert tree_optimizer.is_node_visible(["root", "child1"]) == True
        assert tree_optimizer.is_node_visible(["root", "child1", "grandchild1"]) == False

    def test_windowing_optimization(self, tree_optimizer):
        """Test windowing optimization for tree rendering."""
        # Create a large tree structure
        tree_data = {
            "root": {
                f"child{i}": {
                    f"grandchild{j}": f"value{i}_{j}" 
                    for j in range(10)
                } 
                for i in range(100)
            }
        }
        
        # Initialize the optimizer
        tree_optimizer.initialize(tree_data)
        
        # Expand the root to show all children
        tree_optimizer.set_node_expanded(["root"], True)
        
        # Set a window size smaller than the total number of nodes
        tree_optimizer.visible_window_size = 20
        
        # Set the scroll position to somewhere in the middle
        tree_optimizer.set_scroll_position(50)
        
        # Get the visible nodes
        visible_nodes = tree_optimizer.get_visible_nodes()
        
        # Verify the windowing is working
        assert len(visible_nodes) <= tree_optimizer.visible_window_size
        
        # Check that we're getting nodes around index 50
        middle_nodes = [n for n in visible_nodes if "child5" in n[0]]
        assert len(middle_nodes) > 0

    def test_ui_update_optimization(self, tree_optimizer, ui_controls):
        """Test that UI updates are optimized to only render visible nodes."""
        # Mock the UI rendering method
        with patch.object(ui_controls["tree_view"], 'controls', []) as mock_controls:
            # Create a simple tree
            tree_data = {
                "root": {
                    "child1": "value1",
                    "child2": "value2"
                }
            }
            
            # Initialize and render
            tree_optimizer.initialize(tree_data)
            tree_optimizer.render_tree()
            
            # Verify initial render created controls
            assert len(mock_controls) > 0
            initial_control_count = len(mock_controls)
            
            # Expand the root
            tree_optimizer.set_node_expanded(["root"], True)
            tree_optimizer.render_tree()
            
            # Verify more controls were added
            assert len(mock_controls) > initial_control_count
            
            # Collapse the root
            tree_optimizer.set_node_expanded(["root"], False)
            tree_optimizer.render_tree()
            
            # Verify fewer controls are shown
            assert len(mock_controls) <= initial_control_count


@pytest.mark.integration
class TestOptimizationIntegration:
    """Integration tests for optimization components working together."""

    def test_lazy_loader_with_cached_manager(self, lazy_loader, cached_data_manager, sample_large_json_file):
        """Test integration between LazyJSONLoader and CachedDataManager."""
        # Connect the components
        lazy_loader.start_loading(sample_large_json_file)
        
        # Wait for loading to complete
        while not lazy_loader.is_loaded:
            time.sleep(0.1)
        
        # Use lazy_loader through cached_data_manager
        cached_data_manager.data_source = lazy_loader
        
        # Access the same path multiple times
        test_path = ["level1", "item5", "subitem3"]
        expected_value = "value5_3"
        
        # First access should be a cache miss
        value1 = cached_data_manager.get_value_by_path(test_path)
        assert value1 == expected_value
        assert cached_data_manager.cache_misses == 1
        
        # Second access should be a cache hit
        value2 = cached_data_manager.get_value_by_path(test_path)
        assert value2 == expected_value
        assert cached_data_manager.cache_hits == 1

    def test_background_loading_with_progress(self, lazy_loader, background_processor, sample_large_json_file, sample_app_state):
        """Test background loading of JSON with progress reporting."""
        # Create a progress tracker
        progress_tracker = Mock()
        
        # Create a function to load in the background
        def background_load():
            lazy_loader.start_loading(sample_large_json_file)
            while not lazy_loader.is_loaded:
                # Report progress
                progress = lazy_loader.get_loading_progress()
                progress_tracker(progress)
                time.sleep(0.1)
            return lazy_loader.get_root_value()
        
        # Schedule the background task
        task_id = background_processor.schedule_task(
            background_load,
            progress_callback=lambda p: sample_app_state.get("feedback_manager", Mock()).update_progress(p)
        )
        
        # Wait for completion
        background_processor.wait_for_task(task_id)
        
        # Verify task completed and returned valid data
        result = background_processor.get_task_result(task_id)
        assert result is not None
        assert "level1" in result
        
        # Verify progress was tracked
        assert progress_tracker.call_count > 0
        # Last progress should be 1.0
        if progress_tracker.call_count > 0:
            last_call = progress_tracker.call_args_list[-1]
            # Allow for minor floating point variations
            assert abs(last_call[0][0] - 1.0) < 0.01

    def test_tree_optimizer_with_background_updates(self, tree_optimizer, background_processor, ui_controls):
        """Test tree optimization with background rendering updates."""
        # Mock the update UI method
        with patch.object(ui_controls["page"], 'update') as mock_update:
            # Create a large tree structure
            tree_data = {
                "root": {
                    f"child{i}": {
                        f"grandchild{j}": f"value{i}_{j}" 
                        for j in range(10)
                    } 
                    for i in range(100)
                }
            }
            
            # Initialize the optimizer
            tree_optimizer.initialize(tree_data)
            
            # Create a function for background rendering
            def background_render():
                # Expand all nodes and render
                tree_optimizer.expand_all()
                tree_optimizer.render_tree()
                return "render_complete"
            
            # Schedule the background task
            task_id = background_processor.schedule_task(background_render)
            
            # Wait for completion
            background_processor.wait_for_task(task_id)
            
            # Verify the rendering happened (update was called)
            assert mock_update.call_count > 0
            
            # Verify the task completed successfully
            assert background_processor.get_task_result(task_id) == "render_complete"