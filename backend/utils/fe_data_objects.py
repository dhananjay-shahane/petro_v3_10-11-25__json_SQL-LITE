import pandas as pd
import csv
import pickle
import json
import matplotlib.pyplot as plt
import lasio
from dataclasses import dataclass, field
from scipy.interpolate import interp1d
from typing import List, Dict, Any
from datetime import datetime
import logging
import numpy as np
import math
from typing import Union
from typing import Literal

# Configure logging
logging.basicConfig(level=logging.INFO)
# Define the custom type for interp attribute
interpolation_type = Literal["POINT", "TOP", "CONTINUOUS"]
# Define the custom type for value type
value_type = Literal["str", "float"]
@dataclass
class Constant:
    name: str
    value: Union[float,str, datetime]
    tag: str
    
@dataclass
class Constants:
    constants: List[Constant]
    
    
@dataclass
class RESSUM:
    well: str
    interval: str
    top: float
    bottom: float
    gross: float
    phiec: float
    swec: float
    vshc: float
    phie: float
    swe: float
    vsh: float
    phih: float
    sophih: float
    netpay: float
    ntg: float
    dataset: str
    reference: str

def item_data_list_to_dataframe(constant_list: Constants) -> pd.DataFrame:
    # Create a list of dictionaries from the ItemData instances
    data = [
        {
            'Checked': False,  # Add a default value for the 'Checked' column
            'name': const.name,
            'value': const.value,
            'desc': 'Desc'
        }
        for const in constant_list
    ]
    
    # Convert the list of dictionaries into a DataFrame
    return pd.DataFrame(data)

class LogFrame(pd.DataFrame):
    # Define the static log types
    class LogType:
        INDEX = "Index"
        VARIABLE = "Variable"
        TOP = "Top"

    def __init__(self, data=None, index=None, columns=None, **kwargs):
        # Initialize the DataFrame with provided data
        super().__init__(data=data, index=index, columns=columns, **kwargs)
        # Ensure the DataFrame has the 'DEPT' column
        required_column = 'DEPT'
        if required_column not in self.columns:
            raise ValueError(f"DataFrame must contain the column: {required_column}")

    def get_log_summary(self):
        # Example method to get a summary of the DataFrame
        return self.describe()

    def to_dict(self) -> Dict[str, Any]:
        """Convert WellLog DataFrame to dictionary."""
        return {
            'columns': self.columns.tolist(),
            'index': self.index.tolist(),
            'data': self.values.tolist()
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'LogFrame':
        """Create a LogFrame DataFrame from a dictionary."""
        df = pd.DataFrame(data['data'], columns=data['columns'])
        df.index = data['index']
        return LogFrame(df)

    def serialize(self, filename: str):
        """Serialize LogFrame to a file."""
        with open(filename, 'wb') as file:
            pickle.dump(self, file)

    @staticmethod
    def deserialize(filename: str) -> 'LogFrame':
        """Deserialize WellLog from a file."""
        with open(filename, 'rb') as file:
            return pickle.load(file)

    def filter_by_depth(self, min_depth: float, max_depth: float) -> 'LogFrame':
        """Filter WellLog data by depth range."""
        if min_depth >= max_depth:
            raise ValueError("Minimum depth must be less than maximum depth.")
        filtered_data = self[(self['DEPT'] >= min_depth) & (self['DEPT'] <= max_depth)]
        return LogFrame(filtered_data)

    def add_log(self, name: str, data: List[float]) -> None:
        """Add a new log to the WellLog."""
        if name in self.columns:
            raise ValueError(f"Log '{name}' already exists.")
        self[name] = data

    def plot(self, logs: List[str] = None, depth_column: str = 'DEPT', title: str = 'Well Log', xlabel: str = 'Value', ylabel: str = 'Depth'):
        """Plot WellLog data using matplotlib."""
        if logs is None:
            logs = self.columns.tolist()
        if depth_column not in self.columns:
            raise ValueError(f"Depth column '{depth_column}' not found in WellLog.")
        if not logs:
            logs = [col for col in self.columns if col != depth_column]

        plt.figure(figsize=(12, 8))
        for log in logs:
            if log == depth_column:
                continue
            plt.plot(self[log], self[depth_column], label=log)
        
        plt.ylabel(ylabel)
        plt.xlabel(xlabel)
        plt.title(title)
        plt.legend()
        plt.grid(True)
        plt.show()
        
@dataclass
class WellLog:
    """Data class representing a well log."""
    name: str
    date: str
    description: str
    log: List[Union[str, float]]  # New attribute for log values
    log_type: value_type
    interpolation: interpolation_type
    dtst: str

    def __init__(self, name: str, date: str, description: str, interpolation: interpolation_type, log_type: value_type, log: List[Union[str, float]], dtst: str):
        # Enforce that all values are either str or numeric (int/float), allowing None for missing values
        if not log:
            self.name = name
            self.date = date
            self.description = description
            self.log = log
            self.log_type = log_type
            self.interpolation = interpolation
            self.dtst = dtst
            return
        
        # Filter out None values for type checking
        non_none_values = [v for v in log if v is not None]
        
        if non_none_values:
            # Check if all non-None values are numeric (int or float) OR all are strings
            all_numeric = all(isinstance(v, (int, float)) for v in non_none_values)
            all_strings = all(isinstance(v, str) for v in non_none_values)
            
            if not (all_numeric or all_strings):
                raise ValueError("All elements of 'values' must be of the same category: either all numeric (int/float) or all str.")
            
            # Convert all numeric values to float for consistency, keeping None as is
            if all_numeric:
                log = [float(v) if v is not None else None for v in log]

        # Assign the validated values to the instance
        self.name = name
        self.date = date
        self.description = description
        self.log = log
        self.log_type = log_type
        self.interpolation = interpolation
        self.dtst = dtst
        
    def __post_init__(self):
        
        # Enforce that all elements in 'values' match the specified 'values_type'
        if self.log_type == "str":
            if not all(isinstance(v, str) for v in self.values):
                raise ValueError("All elements in 'values' must be of type 'str'.")
        elif self.log_type == "float":
            if not all(isinstance(v, float) for v in self.values):
                raise ValueError("All elements in 'values' must be of type 'float'.")
        else:
            raise ValueError("Invalid 'values_type'. Must be either 'str' or 'float'.")
        
        # Ensures that 'interp' is one of the allowed values if not using Literal
        if self.interp not in {"POINT", "TOP", "CONTINUOUS"}:
            raise ValueError(f"Invalid value for interp. Must be one of: 'POINT', 'CONTINUOUS', 'TOP'.")
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert WellLog to a dictionary for JSON serialization."""
        return {
            "name": self.name,
            "date": self.date,
            "description": self.description,
            "interpolation": self.interpolation,
            "log_type": self.log_type,
            "log": self.log,  # Serialize the logs
            "dtst": self.dtst,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'WellLog':
        """Create a WellLog from a dictionary."""
        return WellLog(
            name=data['name'],
            date=data['date'],
            description=data['description'],
            interpolation= data['interpolation'],
            log_type= data['log_type'],
            log=data['log'],  # Deserialize the 
            dtst=data['dtst'],
        )

@dataclass
class Dataset:
    """Data class representing a dataset of well logs."""
    date_created: datetime
    name: str
    type: str
    wellname: str
    constants: List[Constant] = field(default_factory=list)
    index_log: List[float] = field(default_factory=list)
    index_name: str = ""
    well_logs: List[WellLog] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Dataset to a dictionary for JSON serialization."""
        return {
            "date_created": self.date_created.isoformat(),
            "name": self.name,
            "type": self.type,
            "wellname": self.wellname,
            "constants": [vars(constant) for constant in self.constants],
            "index_log": self.index_log,
            "index_name": self.index_name,
            "well_logs": [log.to_dict() for log in self.well_logs],
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Dataset':
        """Create a Dataset from a dictionary."""
        constants = [Constant(**constant) for constant in data['constants']]
        well_logs = [WellLog.from_dict(log) for log in data['well_logs']]
        date_created = datetime.fromisoformat(data['date_created'])
        return Dataset(
            date_created=date_created,
            name=data['name'],
            type=data['type'],
            wellname=data['wellname'],
            constants=constants,
            index_log=data['index_log'],
            index_name=data['index_name'],
            well_logs=well_logs,
            metadata=data['metadata'],
        )

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert Dataset to a pandas DataFrame for easy manipulation and plotting.
        
        Returns:
            pd.DataFrame: DataFrame with index_log as index and well_logs as columns
        """
        data_dict = {}
        
        if self.index_log and self.index_name:
            data_dict[self.index_name] = self.index_log
        
        for well_log in self.well_logs:
            data_dict[well_log.name] = well_log.log
        
        df = pd.DataFrame(data_dict)
        
        if self.index_name and self.index_name in df.columns:
            df.set_index(self.index_name, inplace=True)
        
        return df

    def export_to_las(self, output_path: str, well_name: str = None) -> bool:
        """
        Export Dataset to a LAS (Log ASCII Standard) file.
        
        Args:
            output_path: Path where the LAS file will be saved
            well_name: Name of the well (defaults to dataset wellname)
            
        Returns:
            bool: True if export successful, False otherwise
        """
        try:
            las = lasio.LASFile()
            
            well_name = well_name or self.wellname
            las.well.WELL = lasio.HeaderItem('WELL', value=well_name)
            las.well.DATE = lasio.HeaderItem('DATE', value=self.date_created.strftime('%Y-%m-%d'))
            
            if self.index_log and self.index_name:
                index_data = np.array(self.index_log)
                
                df_data = {self.index_name: index_data}
                for log in self.well_logs:
                    log_data = np.array(log.log)
                    if len(log_data) == len(index_data):
                        df_data[log.name] = log_data
                
                df = pd.DataFrame(df_data)
                df.set_index(self.index_name, inplace=True)
                las.set_data_from_df(df)
            
            las.write(output_path, version=2.0)
            return True
        except Exception as e:
            print(f"Error exporting to LAS: {e}")
            return False

    @staticmethod
    def from_csv(filename: str, dataset_name: str, dataset_type: str, well_name: str) -> 'Dataset':
        """Create a Dataset from a CSV file."""
        df = pd.read_csv(filename)
        index_name = 'DEPT'
        if index_name not in df.columns:
            raise ValueError(f"CSV file must contain the column: {index_name}")

        index_log = df[index_name].tolist()
        df_logs = df.drop(columns=[index_name])
        logs=[]
        for col_index, column in df_logs.columns:
            l= WellLog(name=column, date=datetime,description='',log=df_logs.iloc[col_index])
            logs.append(l)
        
        well_logs = [WellLog(name=column, date=datetime.now().isoformat(), 
                             description='Created from CSV', log=logs, dtst='CSV') 
                     for column in df_logs.columns]

        return Dataset(
            date_created=datetime.now(),
            name=dataset_name,
            type=dataset_type,
            wellname=well_name,
            index_log=index_log,
            index_name=index_name,
            well_logs=well_logs,
            metadata={'source': 'CSV import'}
        )

    @staticmethod
    def from_las(filename: str, dataset_name: str, dataset_type: str, well_name: str) -> 'Dataset':
        """Create a Dataset from a LAS file using lasio."""
        las = lasio.read(filename)
        df = las.df()
        df.reset_index(inplace=True)
        
        # find which of the possilbe mnemonic for Depth index is used in the LAS file
        possible_index = ['DEPT','DEPTH']
        print(possible_index)
        #found_index = any(item in possible_index for item in df.columns)
        found_index = list(filter(lambda x: x in possible_index, df.columns))
        print('******',found_index)
        
        index_name = found_index[0]
        if index_name not in df.columns:
            raise ValueError(f"LAS file must contain the column: {index_name}")

        index_log = df[index_name].tolist()
        # Replace NaN values with None in index log
        index_log = [None if (isinstance(v, float) and math.isnan(v)) else v for v in index_log]
        #df_logs = df.drop(columns=[index_name])
        # Set interpolation based on dataset type
        interp = "POINT" if dataset_type == 'Point' else "CONTINUOUS"
        logs = []
        for col_index, column in enumerate(df.columns):
            log_values = df.iloc[:, col_index].tolist()  # Get values of the current column as a list
            # Replace NaN values with None to avoid "nan" in JSON
            log_values = [None if (isinstance(v, float) and math.isnan(v)) else v for v in log_values]
            log_type = 'float'
                
            well_log = WellLog(
                name=column,
                date=datetime.now().isoformat(),  # Use current datetime
                description='',  # You can add a description if needed
                interpolation=interp,
                log_type=log_type,
                log=log_values,
                dtst='WIRE'  # Set appropriate dtst value
            )
            log_values=[]
            logs.append(well_log)
        return Dataset(
            date_created=datetime.now(),
            name=dataset_name,
            type=dataset_type,
            wellname=well_name,
            index_log=index_log,
            index_name=index_name,
            well_logs=logs,
            metadata={'source': 'LAS import'}
        )
    @staticmethod
    def from_las_attachement(las_file_content, dataset_name: str, dataset_type: str, well_name: str) -> 'Dataset':
        """Create a Dataset from a LAS file using lasio."""
        import io
        las_file_like = io.StringIO(las_file_content)
        las = lasio.read(las_file_like)
        df = las.df()
        df.reset_index(inplace=True)
        
        # find which of the possilbe mnemonic for Depth index is used in the LAS file
        possible_index = ['DEPT','DEPTH']
        print(possible_index)
        #found_index = any(item in possible_index for item in df.columns)
        found_index = list(filter(lambda x: x in possible_index, df.columns))
        print('******',found_index)
        
        index_name = found_index[0]
        if index_name not in df.columns:
            raise ValueError(f"LAS file must contain the column: {index_name}")

        index_log = df[index_name].tolist()
        # Replace NaN values with None in index log
        index_log = [None if (isinstance(v, float) and math.isnan(v)) else v for v in index_log]
        #df_logs = df.drop(columns=[index_name])
        # Set interpolation based on dataset type
        interp = "POINT" if dataset_type == 'Point' else "CONTINUOUS"
        logs = []
        for col_index, column in enumerate(df.columns):
            log_values = df.iloc[:, col_index].tolist()  # Get values of the current column as a list
            # Replace NaN values with None to avoid "nan" in JSON
            log_values = [None if (isinstance(v, float) and math.isnan(v)) else v for v in log_values]
            log_type = 'float'
                
            well_log = WellLog(
                name=column,
                date=datetime.now().isoformat(),  # Use current datetime
                description='',  # You can add a description if needed
                interpolation=interp,
                log_type=log_type,
                log=log_values,
                dtst='WIRE'  # Set appropriate dtst value
            )
            log_values=[]
            logs.append(well_log)
        return Dataset(
            date_created=datetime.now(),
            name=dataset_name,
            type=dataset_type,
            wellname=well_name,
            index_log=index_log,
            index_name=index_name,
            well_logs=logs,
            metadata={'source': 'LAS import'}
        )
    @staticmethod
    def reference(top, bottom, dataset_name: str, dataset_type: str, well_name: str) -> 'Dataset':
        """Create a Refrence Dataset from a LAS file using lasio."""
  

        # find which of the possilbe mnemonic for Depth index is used in the LAS file
        index = 'DEPTH' # Always use 'DEPTH' as reference
        interp = "CONTINUOUS"
        bot = math.ceil(bottom)
        refvalues = np.arange(0, bot, 0.5).tolist()  # Includes 2000.0
        index_log = refvalues
        #df_logs = df.drop(columns=[index_name])
        logs = []
        log_values = refvalues
        log_type = 'float'  
        well_log = WellLog(
            name=index,
            date=datetime.now().isoformat(),  # Use current datetime
            description='',  # You can add a description if needed
            interpolation=interp,
            log_type=log_type,
            log=log_values,
            dtst='WIRE'  # Set appropriate dtst value
        )

        logs.append(well_log)
        return Dataset(
            date_created=datetime.now(),
            name=dataset_name,
            type=dataset_type,
            wellname=well_name,
            index_log=index_log,
            index_name=index,
            well_logs=logs,
            metadata={'source': 'Created with new well creation'}
        )
    @staticmethod
    def well_header(dataset_name: str, dataset_type: str, well_name: str) -> 'Dataset':
        """Create a WELL_HEADER Dataset from a LAS file using lasio."""
  

        # find which of the possilbe mnemonic for Depth index is used in the LAS file
        index = 'DEPTH' # Always use 'DEPTH' as reference
       

        return Dataset(
            date_created=datetime.now(),
            name=dataset_name,
            type=dataset_type,
            wellname=well_name,
            metadata={'source': 'Created with new well creation'}
        )

@dataclass
class Well:
    """Data class representing a well."""
    date_created: datetime
    well_name: str
    well_type: str
    datasets: List[Dataset] = field(default_factory=list)

    def add_dataset(self, dataset: Dataset):
        """Add a Dataset to the Well."""
        self.datasets.append(dataset)

    def remove_dataset(self, dataset_name: str):
        """Remove a Dataset by its name."""
        self.datasets = [ds for ds in self.datasets if ds.name != dataset_name]

    def get_dataset(self, dataset_name: str) -> Dataset:
        """Retrieve a Dataset by its name."""
        for ds in self.datasets:
            if ds.name == dataset_name:
                return ds
        raise ValueError(f"No Dataset found with name: {dataset_name}")

    def to_dataframe(self, dataset_names: List[str] = None) -> pd.DataFrame:
        """
        Convert Well data to a single pandas DataFrame by merging specified datasets.
        
        Args:
            dataset_names: List of dataset names to include. If None, include all datasets.
            
        Returns:
            pd.DataFrame: Merged DataFrame with all datasets
        """
        if dataset_names is None:
            datasets_to_merge = self.datasets
        else:
            datasets_to_merge = [self.get_dataset(name) for name in dataset_names]
        
        if not datasets_to_merge:
            return pd.DataFrame()
        
        dfs = [ds.to_dataframe() for ds in datasets_to_merge]
        
        if len(dfs) == 1:
            return dfs[0]
        
        merged_df = dfs[0]
        for df in dfs[1:]:
            merged_df = merged_df.join(df, how='outer', rsuffix='_dup')
        
        return merged_df

    def summary(self) -> Dict[str, Any]:
        """Generate a summary of the Well, including dataset names."""
        return {
            'well_name': self.well_name,
            'well_type': self.well_type,
            'dataset_names': [ds.name for ds in self.datasets]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert Well to a dictionary."""
        return {
            'date_created': self.date_created.isoformat(),
            'well_name': self.well_name,
            'well_type': self.well_type,
            'datasets': [dataset.to_dict() for dataset in self.datasets]
        }

    def serialize(self, filename: str):
        """Serialize Well to a file."""
        with open(filename, 'w') as file:
            json.dump(self.to_dict(), file, default=str)

    @staticmethod
    def deserialize(filepath: str) -> 'Well':
        """Deserialize Well from a file."""
        with open(filepath, 'r') as file:
            data = json.load(file)
            return Well.from_dict(data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Well':
        """Create Well from a dictionary."""
        datasets = [Dataset.from_dict(ds) for ds in data.get('datasets', [])]
        return Well(
            date_created=datetime.fromisoformat(data['date_created']),
            well_name=data['well_name'],
            well_type=data['well_type'],
            datasets=datasets
        )
@dataclass
class SurveyData:
    depth: float
    deviation: float
    azimuth: float
    def to_dict(self) -> Dict[str, Any]:
        return {
            'depth': self.depth,
            'deviation': self.deviation,
            'azimuth': self.azimuth
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SurveyData':
        return SurveyData(
            depth=data['depth'],
            deviation=data['deviation'],
            azimuth=data['azimuth']
        )

@dataclass
class Survey:
    data: List[SurveyData] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'data': [survey_data.to_dict() for survey_data in self.data]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Survey':
        survey_data = [SurveyData.from_dict(item) for item in data['data']]
        return cls(data=survey_data)

    def add_data(self, survey_data: SurveyData):
        self.data.append(survey_data)
        
    def import_from_csv(self, file_path: str):
        with open(file_path, mode='r') as file:
            reader = csv.reader(file)
            # Skip the header if there is one
            next(reader, None)
            for row in reader:
                depth, deviation, azimuth = map(float, row)
                self.add_data(SurveyData(depth, deviation, azimuth))
                
    def compute_tvd_minimum_curvature(depths, deviations, azimuths):
        """Compute Total Vertical Depth (TVD) using the Minimum Curvature method."""
        tvds = [depths[0]]  # TVD at the first depth point
        norths = [0]  # TVD at the first depth point
        souths = [0]  # TVD at the first depth point
        cumulative_tvd = [depths[0]]  # Cumulative TVD starts with the first depth point
        pi = 3.141592653589793
        for i in range(1, len(depths)):
            D = depths[i] - depths[i - 1]  # Calculate vertical distance
            deviation_radians = np.radians(0.5*(deviations[i - 1]+deviations[i]))  # Convert deviation to radians
            azimuth_radians = np.radians(0.5*(azimuths[i - 1]+azimuths[i]))  # Convert deviation to radians

            # Calculate vertical depth change using the deviation
            vertical_distance = D * np.cos(deviation_radians)
            
            # Calculate vertical depth change using the deviation
            horizontl_distance = D * np.sin(deviation_radians)
            north = horizontl_distance*np.cos(azimuth_radians)
            south = horizontl_distance*np.sin(azimuth_radians)
            # Update TVD without constraints
            new_tvd = tvds[i - 1] + vertical_distance
            new_north = norths[i-1] + north
            new_south = souths[i-1] + south
            
            tvds.append(new_tvd)
            norths.append(new_north)
            souths.append(new_south)
        return tvds, norths, souths

    def interpolate(self, step: float = 0.5) -> List[SurveyData]:
        depths = np.array([d.depth for d in self.data])
        deviations = np.array([d.deviation for d in self.data])
        azimuths = np.array([d.azimuth for d in self.data])

        # Create interpolators
        deviation_interp = interp1d(depths, deviations, kind='linear', fill_value="extrapolate")
        azimuth_interp = interp1d(depths, azimuths, kind='linear', fill_value="extrapolate")

        # Generate new depth values at specified intervals
        new_depths = np.arange(depths.min(), depths.max() + step, step)

        # Interpolate to find corresponding values
        new_deviations = deviation_interp(new_depths)
        new_azimuths = azimuth_interp(new_depths)

        # Combine interpolated data into new list of SurveyData instances
        interpolated_data = [
            SurveyData(depth, deviation, azimuth) 
            for depth, deviation, azimuth in zip(new_depths, new_deviations, new_azimuths)
        ]

        return interpolated_data
class Interpolation:
    # Define the allowed constant values
    ALLOWED_VALUES = {"POINT", "TOPS", "CONTINUOUS"}

    def __init__(self, attribute):
        self._attribute = None  # Initialize the private attribute
        self.attribute = attribute  # Use the setter to validate the value

    @property
    def attribute(self):
        return self._attribute

    @attribute.setter
    def attribute(self, value):
        if value not in Interpolation.ALLOWED_VALUES:
            raise ValueError(f"Invalid value! Allowed values are: {MyClass.ALLOWED_VALUES}")
        self._attribute = value

# Example usage
if __name__ == "__main__":
    survey = Survey()
    
    # Adding original data
    survey.add_data(SurveyData(348.00, 0.00, 0.00))
    survey.add_data(SurveyData(355.00, 1.10, 100.34))
    survey.add_data(SurveyData(385.00, 1.60, 206.30))
    survey.add_data(SurveyData(416.20, 4.90, 239.40))
    survey.add_data(SurveyData(444.40, 7.38, 241.15))
    
    # Interpolating data
    interpolated_data = survey.interpolate(step=0.5)

