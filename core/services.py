from abc import ABC, abstractmethod
from typing import Any


class UseCase(ABC):
    """
    Abstract base class for use cases that can be called like functions.
    """
    
    def __call__(self, **kwargs) -> Any:
        try:
            return self.execute(**kwargs)
            
        except Exception as e:
            raise
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Main execution method to be implemented by concrete use cases.
        
        Args:
            **kwargs: Input parameters for the use case.
            
        Returns:
            The result of the use case execution.
        """
        pass