import yaml
import dataclasses
from collections import OrderedDict


class DataclassYamlSaveLoadMixin:
    @classmethod
    def from_yaml(cls, file_path: str):
        """
        Load current dataclass from a yaml file.
        """
        with open(file_path, "r") as file:
            data_dict = yaml.safe_load(file)
        return cls(**data_dict)

    def to_yaml(self, file_path: str):
        """
        Save current dataclass from a yaml file.
        """
        data_dict = dataclasses.asdict(self, dict_factory=OrderedDict)
        with open(file_path, "w") as file:
            yaml.dump(self, file)