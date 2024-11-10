from abc import ABC, abstractmethod
from typing import Any


class Service(ABC):
    """
    Abstract base class for services that can be called like functions.
    """
    
    def __call__(self, **kwargs) -> Any:
        try:
            return self.execute(**kwargs)
            
        except Exception as e:
            raise
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Main execution method to be implemented by concrete services.
        
        Args:
            **kwargs: Input parameters for the service.
            
        Returns:
            The result of the service execution.
        """
        pass