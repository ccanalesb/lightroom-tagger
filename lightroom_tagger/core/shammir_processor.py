"""Shammir processor that coordinates job execution and error recovery."""

from typing import Dict, Any, List, Optional
import time
import json
from pathlib import Path

from .shammir_navigator import ShammirNavigator
from .shammir_partitioner import ShammirShare


class ShammirProcessor:
    """Coordinates Shammir job execution and error recovery."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.navigator = ShammirNavigator(config)
        self.session_id: Optional[str] = None
        self.current_job_id: Optional[str] = None
        self.error_state: Optional[Dict[str, Any]] = None
        self.retry_count: int = 0
        self.max_retries: int = config.get('max_retries', 3)
        self.retry_delay: int = config.get('retry_delay', 5)

    def start_job(self, job_id: str, session_id: str, content_count: int) -> bool:
        """
        Start a new Shammir job.

        Args:
            job_id: Unique job identifier
            session_id: Session identifier
            content_count: Total content items to process

        Returns:
            True if job started successfully, False otherwise
        """
        self.current_job_id = job_id
        self.session_id = session_id
        self.error_state = None
        self.retry_count = 0

        print(f"Starting job {job_id} with session {session_id}")

        if not self.navigator.start_session(session_id, content_count):
            print("Failed to start session")
            return False

        return True

    def execute_job(self) -> bool:
        """
        Execute the current job.

        Returns:
            True if job completed successfully, False otherwise
        """
        if not self.session_id:
            print("No active session")
            return False

        try:
            while self.navigator.current_partition < self.navigator.total_partitions:
                # Navigate to next partition
                if not self.navigator.navigate_to_next_partition():
                    print("Navigation failed")
                    return self._handle_error("navigation_failed")

                # Process partition
                if not self.navigator.process_current_partition():
                    print("Processing failed")
                    return self._handle_error("processing_failed")

                # Generate and verify shares
                shares = self.navigator.generate_shares()
                if not self.navigator.verify_current_partition():
                    print("Verification failed")
                    return self._handle_error("verification_failed")

                # Persist session state
                if not self.navigator.persist_session():
                    print("State persistence failed")
                    return self._handle_error("persistence_failed")

                # Update progress
                progress = self.navigator.get_progress()
                print(f"Progress: {progress:.1f}%")

            print("Job completed successfully")
            return True

        except Exception as e:
            print(f"Job execution failed: {e}")
            return self._handle_error("execution_failed")

    def _handle_error(self, error_type: str) -> bool:
        """
        Handle errors with retry logic.

        Args:
            error_type: Type of error that occurred

        Returns:
            True if recovery succeeded, False if giving up
        """
        self.error_state = {
            'type': error_type,
            'timestamp': time.time(),
            'retry_count': self.retry_count
        }

        self.retry_count += 1

        if self.retry_count > self.max_retries:
            print(f"Max retries ({self.max_retries}) exceeded")
            return False

        print(f"Error: {error_type}, retry {self.retry_count}/{self.max_retries}")

        # Wait before retrying
        time.sleep(self.retry_delay)

        # Try to restore session and continue
        if not self.navigator.restore_session(self.session_id):
            print("Failed to restore session")
            return False

        return True

    def get_progress(self) -> float:
        """
        Get the current job progress.

        Returns:
            Progress as a percentage (0-100)
        """
        if not self.navigator:
            return 0.0
        return self.navigator.get_progress()

    def cancel_job(self) -> bool:
        """
        Cancel the current job.

        Returns:
            True if cancellation succeeded, False otherwise
        """
        print("Cancelling job")
        self.navigator.close()
        return True

    def get_error_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the current error state.

        Returns:
            Error state information or None if no error
        """
        return self.error_state

    def close(self):
        """Close the processor and clean up resources."""
        self.navigator.close()