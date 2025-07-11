import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.interpolate import interp1d
from scipy import stats
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class WheatPhenologyAnalyzer:
    def __init__(self, ndvi_file, sowing_date, harvest_date):
        """
        Initialize the wheat phenology analyzer
        
        Parameters:
        ndvi_file: Path to NDVI CSV file
        sowing_date: Sowing date (str format: 'DD.MM.YYYY')
        harvest_date: Harvest date (str format: 'DD.MM.YYYY')
        """
        self.ndvi_file = ndvi_file
        self.sowing_date = datetime.strptime(sowing_date, '%d.%m.%Y')
        self.harvest_date = datetime.strptime(harvest_date, '%d.%m.%Y')
        
        # Growth stage definitions
        self.growth_stages = {
            'Sowing': {'ndvi_range': (0.0, 0.1), 'duration_days': 7},
            'Emergence': {'ndvi_range': (0.1, 0.3), 'duration_days': 14},
            'Tillering': {'ndvi_range': (0.3, 0.5), 'duration_days': 30},
            'Stem Elongation': {'ndvi_range': (0.5, 0.7), 'duration_days': 25},
            'Booting': {'ndvi_range': (0.7, 0.8), 'duration_days': 15},
            'Heading': {'ndvi_range': (0.8, 0.9), 'duration_days': 10},
            'Flowering': {'ndvi_range': (0.85, 0.95), 'duration_days': 10},
            'Grain Filling': {'ndvi_range': (0.8, 0.9), 'duration_days': 35},
            'Maturity': {'ndvi_range': (0.4, 0.7), 'duration_days': 20},
            'Harvest': {'ndvi_range': (0.2, 0.5), 'duration_days': 5}
        }
        
        # FVC parameters (will be estimated from data)
        self.fvc_params = {
            'ndvi_soil': None,
            'ndvi_vegetation': None
        }
        
        self.load_data()
        
    def load_data(self):
        """Load and preprocess NDVI data"""
        # Read the NDVI data
        self.ndvi_data = pd.read_csv(self.ndvi_file)
        
        # Clean column names and convert to datetime
        self.ndvi_data.columns = ['phenomenonTime', 'NDVI']
        self.ndvi_data['phenomenonTime'] = pd.to_datetime(self.ndvi_data['phenomenonTime'])
        
        # Sort by date
        self.ndvi_data = self.ndvi_data.sort_values('phenomenonTime').reset_index(drop=True)
        
        print(f"Loaded {len(self.ndvi_data)} NDVI observations")
        print(f"Date range: {self.ndvi_data['phenomenonTime'].min()} to {self.ndvi_data['phenomenonTime'].max()}")
        
    def estimate_fvc_parameters(self, method='seasonal'):
        """
        Estimate FVC parameters using different methods
        
        Parameters:
        method: Parameter estimation method ('literature', 'data_driven', 'seasonal')
        
        Returns:
        dict: Estimated FVC parameters
        """
        if method == 'literature':
            # Literature-based defaults for wheat
            self.fvc_params = {
                'ndvi_soil': 0.15,      # Typical bare soil NDVI for agricultural fields
                'ndvi_vegetation': 0.85  # Typical peak vegetation NDVI for wheat
            }
            print("Using literature-based FVC parameters:")
            
        elif method == 'data_driven':
            # Data-driven estimation using min/max values
            ndvi_min = self.ndvi_data['NDVI'].min()
            ndvi_max = self.ndvi_data['NDVI'].max()
            
            # Add small buffer to avoid division by zero
            self.fvc_params = {
                'ndvi_soil': max(0.05, ndvi_min - 0.02),
                'ndvi_vegetation': min(0.95, ndvi_max + 0.02)
            }
            print("Using data-driven FVC parameters:")
            
        elif method == 'seasonal':
            # Seasonal analysis using early and peak season values
            days_after_sowing = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
            
            # Early season (first 30 days) for soil NDVI
            early_mask = days_after_sowing <= 30
            if early_mask.sum() > 0:
                ndvi_soil = self.ndvi_data.loc[early_mask, 'NDVI'].quantile(0.25)
            else:
                ndvi_soil = 0.15  # Fallback to literature value
            
            # Peak season (middle 60 days) for vegetation NDVI
            mid_mask = (days_after_sowing >= 60) & (days_after_sowing <= 120)
            if mid_mask.sum() > 0:
                ndvi_vegetation = self.ndvi_data.loc[mid_mask, 'NDVI'].quantile(0.75)
            else:
                ndvi_vegetation = 0.85  # Fallback to literature value
            
            self.fvc_params = {
                'ndvi_soil': max(0.05, ndvi_soil),
                'ndvi_vegetation': min(0.95, ndvi_vegetation)
            }
            print("Using seasonal analysis FVC parameters:")
            
        else:
            raise ValueError("Method must be 'literature', 'data_driven', or 'seasonal'")
        
        print(f"  NDVI_soil: {self.fvc_params['ndvi_soil']:.3f}")
        print(f"  NDVI_vegetation: {self.fvc_params['ndvi_vegetation']:.3f}")
        
        return self.fvc_params
    
    def calculate_fvc(self, ndvi_values):
        """
        Calculate Fractional Vegetation Cover (FVC) from NDVI values
        
        FVC = (NDVI - NDVI_soil) / (NDVI_vegetation - NDVI_soil)
        
        Parameters:
        ndvi_values: Array of NDVI values
        
        Returns:
        array: FVC values (0-1)
        """
        if self.fvc_params['ndvi_soil'] is None or self.fvc_params['ndvi_vegetation'] is None:
            raise ValueError("FVC parameters not estimated. Call estimate_fvc_parameters() first.")
        
        ndvi_soil = self.fvc_params['ndvi_soil']
        ndvi_vegetation = self.fvc_params['ndvi_vegetation']
        
        # Calculate FVC
        fvc = (ndvi_values - ndvi_soil) / (ndvi_vegetation - ndvi_soil)
        
        # Clip to valid range [0, 1]
        fvc = np.clip(fvc, 0, 1)
        
        return fvc
    
    def calculate_ground_cover_percentage(self, fvc_values):
        """
        Calculate ground cover percentage from FVC values
        
        Ground Cover % = FVC * 100
        
        Parameters:
        fvc_values: Array of FVC values (0-1)
        
        Returns:
        array: Ground cover percentage values (0-100)
        """
        return fvc_values * 100
    
    def interpolate_ndvi(self, method='balanced'):
        """
        Interpolate NDVI data to daily time series with advanced methods
        
        Parameters:
        method: Interpolation method ('linear', 'cubic', 'polynomial', 'physiological', 'sigmoid', 'balanced')
        """
        # Create daily date range from sowing to harvest
        date_range = pd.date_range(start=self.sowing_date, end=self.harvest_date, freq='D')
        x_interp = (date_range - self.sowing_date).days
        
        if method == 'balanced':
            # Use balanced approach combining physiological knowledge with smooth interpolation
            y_interp = self._balanced_interpolation(x_interp)
        elif method == 'physiological':
            # Use physiological growth curve based on wheat development
            y_interp = self._physiological_interpolation(x_interp)
        elif method == 'sigmoid':
            # Use sigmoid growth curve
            y_interp = self._sigmoid_interpolation(x_interp)
        else:
            # Standard interpolation methods
            x_obs = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
            y_obs = self.ndvi_data['NDVI'].values
            
            if method == 'cubic':
                f_interp = interp1d(x_obs, y_obs, kind='cubic', bounds_error=False, fill_value='extrapolate')
            elif method == 'polynomial':
                coeffs = np.polyfit(x_obs, y_obs, min(3, len(x_obs)-1))
                f_interp = lambda x: np.polyval(coeffs, x)
            else:
                f_interp = interp1d(x_obs, y_obs, kind='linear', bounds_error=False, fill_value='extrapolate')
            
            y_interp = f_interp(x_interp)
        
        # Clip NDVI values to valid range [0, 1]
        y_interp = np.clip(y_interp, 0, 1)
        
        # Create confidence intervals using bootstrap
        x_obs = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
        y_obs = self.ndvi_data['NDVI'].values
        confidence_intervals = self._calculate_confidence_intervals(x_obs, y_obs, x_interp, method)
        
        # Clip confidence intervals to valid range [0, 1]
        confidence_intervals['lower'] = np.clip(confidence_intervals['lower'], 0, 1)
        confidence_intervals['upper'] = np.clip(confidence_intervals['upper'], 0, 1)
        
        # Calculate FVC if parameters are available
        fvc_interp = None
        fvc_lower_ci = None
        fvc_upper_ci = None
        ground_cover_interp = None
        ground_cover_lower_ci = None
        ground_cover_upper_ci = None
        
        if self.fvc_params['ndvi_soil'] is not None:
            fvc_interp = self.calculate_fvc(y_interp)
            fvc_lower_ci = self.calculate_fvc(confidence_intervals['lower'])
            fvc_upper_ci = self.calculate_fvc(confidence_intervals['upper'])
            
            # Calculate ground cover percentage
            ground_cover_interp = self.calculate_ground_cover_percentage(fvc_interp)
            ground_cover_lower_ci = self.calculate_ground_cover_percentage(fvc_lower_ci)
            ground_cover_upper_ci = self.calculate_ground_cover_percentage(fvc_upper_ci)
        
        # Create daily dataframe
        self.daily_ndvi = pd.DataFrame({
            'Date': date_range,
            'Days_After_Sowing': x_interp,
            'NDVI_Interpolated': y_interp,
            'NDVI_Lower_CI': confidence_intervals['lower'],
            'NDVI_Upper_CI': confidence_intervals['upper']
        })
        
        # Add FVC columns if calculated
        if fvc_interp is not None:
            self.daily_ndvi['FVC_Interpolated'] = fvc_interp
            self.daily_ndvi['FVC_Lower_CI'] = fvc_lower_ci
            self.daily_ndvi['FVC_Upper_CI'] = fvc_upper_ci
            
            # Add ground cover percentage columns
            self.daily_ndvi['Ground_Cover_Percentage'] = ground_cover_interp
            self.daily_ndvi['Ground_Cover_Lower_CI'] = ground_cover_lower_ci
            self.daily_ndvi['Ground_Cover_Upper_CI'] = ground_cover_upper_ci
        
        return self.daily_ndvi
    
    def _balanced_interpolation(self, x_interp):
        """
        Balanced interpolation combining physiological knowledge with smooth transitions
        """
        # Convert to numpy array for indexing
        x_interp = np.array(x_interp)
        
        # Get observed data
        x_obs = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
        y_obs = self.ndvi_data['NDVI'].values
        
        # Create a smooth baseline curve using sigmoid
        peak_ndvi = np.max(y_obs)
        peak_day = np.mean(x_obs)  # Use observed data to estimate peak timing
        
        # Create smooth sigmoid baseline with better calibration
        k = 0.02  # Adjusted growth rate
        baseline = 0.05
        sigmoid_baseline = baseline + (peak_ndvi - baseline) / (1 + np.exp(-k * (x_interp - peak_day)))
        
        # Apply physiological constraints with smooth transitions
        y_interp = sigmoid_baseline.copy()
        
        # Define growth stage constraints (soft boundaries)
        emergence_day = 10
        tillering_start = 45
        stem_elongation_start = 120
        booting_start = 200
        flowering_start = 230
        grain_filling_start = 245
        maturity_start = 270
        
        # Apply smooth constraints with higher target values
        for i, days in enumerate(x_interp):
            if days < emergence_day:
                # Before emergence: very low NDVI with smooth transition
                transition = 1 - np.exp(-(emergence_day - days) / 5)
                y_interp[i] = 0.05 * transition + y_interp[i] * (1 - transition)
            elif days < tillering_start:
                # Emergence to tillering: gradual increase
                progress = (days - emergence_day) / (tillering_start - emergence_day)
                target_ndvi = 0.05 + 0.25 * progress
                weight = 0.4  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            elif days < stem_elongation_start:
                # Tillering: moderate increase
                progress = (days - tillering_start) / (stem_elongation_start - tillering_start)
                target_ndvi = 0.30 + 0.35 * progress
                weight = 0.5  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            elif days < booting_start:
                # Stem elongation: rapid increase
                progress = (days - stem_elongation_start) / (booting_start - stem_elongation_start)
                target_ndvi = 0.65 + 0.20 * progress
                weight = 0.6  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            elif days < flowering_start:
                # Booting to flowering: approaching peak
                progress = (days - booting_start) / (flowering_start - booting_start)
                target_ndvi = 0.85 + 0.10 * progress
                weight = 0.7  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            elif days < grain_filling_start:
                # Flowering: peak NDVI
                target_ndvi = 0.95  # Higher peak target
                weight = 0.8  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            elif days < maturity_start:
                # Grain filling: gradual decline
                progress = (days - grain_filling_start) / (maturity_start - grain_filling_start)
                target_ndvi = 0.95 - 0.30 * progress
                weight = 0.6  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
            else:
                # Maturity to harvest: rapid decline
                progress = (days - maturity_start) / (max(x_interp) - maturity_start)
                target_ndvi = 0.65 - 0.50 * progress
                weight = 0.7  # Increased weight
                y_interp[i] = (1 - weight) * y_interp[i] + weight * target_ndvi
        
        # Apply observed data constraints with stronger influence
        for obs_day, obs_ndvi in zip(x_obs, y_obs):
            if obs_day in x_interp:
                idx = np.where(x_interp == obs_day)[0][0]
                # Very strong influence of observed data at measurement points
                y_interp[idx] = 0.9 * obs_ndvi + 0.1 * y_interp[idx]
                
                # Apply stronger influence to nearby points
                for i in range(len(x_interp)):
                    if i != idx:
                        distance = abs(x_interp[i] - obs_day)
                        if distance < 50:  # Extended influence range
                            influence = np.exp(-distance / 15)  # Slower decay
                            y_interp[i] = (1 - influence * 0.5) * y_interp[i] + influence * 0.5 * obs_ndvi
        
        # Apply smoothing filter to remove any remaining spikes
        from scipy.ndimage import gaussian_filter1d
        y_interp = gaussian_filter1d(y_interp, sigma=1.5)  # Reduced smoothing
        
        return y_interp
    
    def _physiological_interpolation(self, x_interp):
        """
        Physiological interpolation based on wheat growth stages and typical NDVI patterns
        """
        # Convert to numpy array for indexing
        x_interp = np.array(x_interp)
        
        # Define key growth stage days (approximate)
        emergence_day = 10
        tillering_start = 45
        stem_elongation_start = 120
        booting_start = 200
        heading_start = 220
        flowering_start = 230
        grain_filling_start = 245
        maturity_start = 270
        
        # Initialize NDVI array
        y_interp = np.zeros_like(x_interp, dtype=float)
        
        for i, days in enumerate(x_interp):
            if days < emergence_day:
                # Before emergence: very low NDVI
                y_interp[i] = 0.05 + 0.02 * np.random.random()
            elif days < tillering_start:
                # Emergence to tillering: gradual increase
                progress = (days - emergence_day) / (tillering_start - emergence_day)
                y_interp[i] = 0.05 + 0.15 * progress
            elif days < stem_elongation_start:
                # Tillering: moderate increase
                progress = (days - tillering_start) / (stem_elongation_start - tillering_start)
                y_interp[i] = 0.20 + 0.25 * progress
            elif days < booting_start:
                # Stem elongation: rapid increase
                progress = (days - stem_elongation_start) / (booting_start - stem_elongation_start)
                y_interp[i] = 0.45 + 0.25 * progress
            elif days < heading_start:
                # Booting: approaching peak
                progress = (days - booting_start) / (heading_start - booting_start)
                y_interp[i] = 0.70 + 0.15 * progress
            elif days < flowering_start:
                # Heading: near peak
                progress = (days - heading_start) / (flowering_start - heading_start)
                y_interp[i] = 0.85 + 0.05 * progress
            elif days < grain_filling_start:
                # Flowering: peak NDVI
                y_interp[i] = 0.90 + 0.02 * np.random.random()
            elif days < maturity_start:
                # Grain filling: gradual decline
                progress = (days - grain_filling_start) / (maturity_start - grain_filling_start)
                y_interp[i] = 0.90 - 0.30 * progress
            else:
                # Maturity to harvest: rapid decline
                progress = (days - maturity_start) / (max(x_interp) - maturity_start)
                y_interp[i] = 0.60 - 0.50 * progress
        
        # Fit observed data points to the physiological curve
        x_obs = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
        y_obs = self.ndvi_data['NDVI'].values
        
        # Adjust the physiological curve to match observed data
        for obs_day, obs_ndvi in zip(x_obs, y_obs):
            if obs_day in x_interp:
                idx = np.where(x_interp == obs_day)[0][0]
                # Blend observed value with physiological curve
                y_interp[idx] = 0.7 * obs_ndvi + 0.3 * y_interp[idx]
        
        return y_interp
    
    def _sigmoid_interpolation(self, x_interp):
        """
        Sigmoid-based interpolation for smooth growth curve
        """
        # Convert to numpy arrays for indexing
        x_interp = np.array(x_interp)
        
        # Find peak NDVI from observed data
        peak_ndvi = self.ndvi_data['NDVI'].max()
        
        # Estimate peak timing (around 230-250 days after sowing for winter wheat)
        peak_day = 240
        
        # Sigmoid parameters
        k = 0.02  # Growth rate
        x0 = peak_day  # Inflection point
        
        # Sigmoid function: S(x) = L / (1 + e^(-k(x-x0)))
        # where L is the maximum value (peak_ndvi)
        y_interp = peak_ndvi / (1 + np.exp(-k * (x_interp - x0)))
        
        # Add baseline NDVI for early stages
        baseline = 0.05
        y_interp = baseline + (peak_ndvi - baseline) * y_interp / peak_ndvi
        
        # Adjust to match observed data points
        x_obs = (self.ndvi_data['phenomenonTime'] - self.sowing_date).dt.days
        y_obs = self.ndvi_data['NDVI'].values
        
        for obs_day, obs_ndvi in zip(x_obs, y_obs):
            if obs_day in x_interp:
                idx = np.where(x_interp == obs_day)[0][0]
                # Blend observed value with sigmoid curve
                y_interp[idx] = 0.8 * obs_ndvi + 0.2 * y_interp[idx]
        
        return y_interp
    
    def _calculate_confidence_intervals(self, x_obs, y_obs, x_interp, method, n_bootstrap=1000):
        """Calculate confidence intervals using bootstrap resampling"""
        # Ensure numpy arrays for indexing
        x_obs = np.array(x_obs)
        y_obs = np.array(y_obs)
        bootstrap_predictions = []
        
        for _ in range(n_bootstrap):
            # Bootstrap sample
            indices = np.random.choice(len(x_obs), len(x_obs), replace=True)
            x_boot = x_obs[indices]
            y_boot = y_obs[indices]
            
            # Remove duplicates for interpolation
            unique_indices = np.unique(x_boot, return_index=True)[1]
            x_boot_unique = x_boot[unique_indices]
            y_boot_unique = y_boot[unique_indices]
            
            # Ensure we have enough points for interpolation
            if len(x_boot_unique) < 2:
                continue
                
            # Interpolate bootstrap sample
            try:
                if method == 'cubic' and len(x_boot_unique) >= 4:
                    f_boot = interp1d(x_boot_unique, y_boot_unique, kind='cubic', 
                                    bounds_error=False, fill_value='extrapolate')
                elif method == 'polynomial' and len(x_boot_unique) >= 3:
                    coeffs = np.polyfit(x_boot_unique, y_boot_unique, min(2, len(x_boot_unique)-1))
                    f_boot = lambda x: np.polyval(coeffs, x)
                else:
                    f_boot = interp1d(x_boot_unique, y_boot_unique, kind='linear', 
                                    bounds_error=False, fill_value='extrapolate')
                
                y_boot_interp = f_boot(x_interp)
                bootstrap_predictions.append(y_boot_interp)
            except:
                # Skip this bootstrap iteration if interpolation fails
                continue
        
        if not bootstrap_predictions:
            # Fallback to simple confidence intervals
            return {'lower': y_interp * 0.95, 'upper': y_interp * 1.05}
        
        bootstrap_predictions = np.array(bootstrap_predictions)
        
        # Calculate percentiles for confidence intervals
        lower = np.percentile(bootstrap_predictions, 2.5, axis=0)
        upper = np.percentile(bootstrap_predictions, 97.5, axis=0)
        
        return {'lower': lower, 'upper': upper}
    
    def estimate_growth_stages(self):
        """Estimate growth stages based on NDVI patterns and timing"""
        # Find peak NDVI (should be around late May to early June)
        peak_idx = self.daily_ndvi['NDVI_Interpolated'].idxmax()
        peak_date = self.daily_ndvi.loc[peak_idx, 'Date']
        peak_ndvi = self.daily_ndvi.loc[peak_idx, 'NDVI_Interpolated']
        
        print(f"Peak NDVI: {peak_ndvi:.3f} on {peak_date.strftime('%Y-%m-%d')}")
        
        # Define growth stage transitions based on NDVI patterns and timing
        growth_stage_dates = {
            'Sowing': self.sowing_date,
            'Emergence': self.sowing_date + timedelta(days=10),
            'Tillering': self.sowing_date + timedelta(days=45),
            'Stem Elongation': self.sowing_date + timedelta(days=120),
            'Booting': peak_date - timedelta(days=20),
            'Heading': peak_date - timedelta(days=10),
            'Flowering': peak_date,
            'Grain Filling': peak_date + timedelta(days=15),
            'Maturity': self.harvest_date - timedelta(days=25),
            'Harvest': self.harvest_date
        }
        
        # Assign growth stages to daily data
        self.daily_ndvi['Growth_Stage'] = 'Unknown'
        
        for stage, date in growth_stage_dates.items():
            mask = self.daily_ndvi['Date'] >= date
            if stage != 'Harvest':
                # Find next stage date
                next_stages = [s for s in growth_stage_dates.keys() if growth_stage_dates[s] > date]
                if next_stages:
                    next_date = min(growth_stage_dates[s] for s in next_stages)
                    mask = mask & (self.daily_ndvi['Date'] < next_date)
                else:
                    mask = mask & (self.daily_ndvi['Date'] <= self.harvest_date)
            else:
                mask = self.daily_ndvi['Date'] == date
            
            self.daily_ndvi.loc[mask, 'Growth_Stage'] = stage
        
        return growth_stage_dates
    
    def create_visualization(self, save_path='wheat_phenology_analysis.png'):
        """Create comprehensive visualization of NDVI, FVC, Ground Cover Percentage, and growth stages"""
        # Create 4-panel layout if ground cover is available, otherwise 3-panel for FVC, or 2-panel for basic
        has_ground_cover = 'Ground_Cover_Percentage' in self.daily_ndvi.columns
        has_fvc = 'FVC_Interpolated' in self.daily_ndvi.columns
        
        if has_ground_cover:
            fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 20))
        elif has_fvc:
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 16))
        else:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
        
        # Color palette for growth stages
        colors = plt.cm.Set3(np.linspace(0, 1, len(self.growth_stages)))
        stage_colors = dict(zip(self.growth_stages.keys(), colors))
        
        # Plot 1: NDVI time series with confidence intervals
        ax1.fill_between(self.daily_ndvi['Date'], 
                        self.daily_ndvi['NDVI_Lower_CI'], 
                        self.daily_ndvi['NDVI_Upper_CI'], 
                        alpha=0.3, color='lightblue', label='95% Confidence Interval')
        
        ax1.plot(self.daily_ndvi['Date'], self.daily_ndvi['NDVI_Interpolated'], 
                'b-', linewidth=2, label='Interpolated NDVI')
        
        # Plot original data points
        ax1.scatter(self.ndvi_data['phenomenonTime'], self.ndvi_data['NDVI'], 
                   color='red', s=100, zorder=5, label='Observed NDVI')
        
        # Add FVC parameters as horizontal lines if available
        if has_fvc:
            ax1.axhline(y=self.fvc_params['ndvi_soil'], color='brown', linestyle='--', 
                       alpha=0.7, label=f'NDVI_soil: {self.fvc_params["ndvi_soil"]:.3f}')
            ax1.axhline(y=self.fvc_params['ndvi_vegetation'], color='green', linestyle='--', 
                       alpha=0.7, label=f'NDVI_vegetation: {self.fvc_params["ndvi_vegetation"]:.3f}')
        
        # Add growth stage regions
        for stage in self.growth_stages.keys():
            stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
            if not stage_data.empty:
                ax1.axvspan(stage_data['Date'].min(), stage_data['Date'].max(), 
                           alpha=0.2, color=stage_colors[stage], label=f'{stage}')
        
        ax1.set_xlabel('Date')
        ax1.set_ylabel('NDVI')
        ax1.set_title('Wheat NDVI Time Series with Growth Stages', fontsize=14, fontweight='bold')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: FVC time series (if available)
        if has_fvc:
            ax2.fill_between(self.daily_ndvi['Date'], 
                            self.daily_ndvi['FVC_Lower_CI'], 
                            self.daily_ndvi['FVC_Upper_CI'], 
                            alpha=0.3, color='lightgreen', label='95% Confidence Interval')
            
            ax2.plot(self.daily_ndvi['Date'], self.daily_ndvi['FVC_Interpolated'], 
                    'g-', linewidth=2, label='Interpolated FVC')
            
            # Add growth stage regions
            for stage in self.growth_stages.keys():
                stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
                if not stage_data.empty:
                    ax2.axvspan(stage_data['Date'].min(), stage_data['Date'].max(), 
                               alpha=0.2, color=stage_colors[stage], label=f'{stage}')
            
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Fractional Vegetation Cover (FVC)')
            ax2.set_title('Wheat FVC Time Series with Growth Stages', fontsize=14, fontweight='bold')
            ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 1)
        
        # Plot 3: Ground Cover Percentage time series (if available)
        if has_ground_cover:
            ax3.fill_between(self.daily_ndvi['Date'], 
                            self.daily_ndvi['Ground_Cover_Lower_CI'], 
                            self.daily_ndvi['Ground_Cover_Upper_CI'], 
                            alpha=0.3, color='peachpuff', label='95% Confidence Interval')
            
            ax3.plot(self.daily_ndvi['Date'], self.daily_ndvi['Ground_Cover_Percentage'], 
                    'orange', linewidth=2, label='Ground Cover Percentage')
            
            # Add growth stage regions
            for stage in self.growth_stages.keys():
                stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
                if not stage_data.empty:
                    ax3.axvspan(stage_data['Date'].min(), stage_data['Date'].max(), 
                               alpha=0.2, color=stage_colors[stage], label=f'{stage}')
            
            ax3.set_xlabel('Date')
            ax3.set_ylabel('Ground Cover Percentage (%)')
            ax3.set_title('Wheat Ground Cover Percentage Time Series with Growth Stages', fontsize=14, fontweight='bold')
            ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax3.grid(True, alpha=0.3)
            ax3.set_ylim(0, 100)
        
        # Plot 4: Growth stage timeline (or Plot 3/2 if fewer panels)
        if has_ground_cover:
            ax_timeline = ax4
        elif has_fvc:
            ax_timeline = ax3
        else:
            ax_timeline = ax2
        
        growth_stage_dates = self.estimate_growth_stages()
        
        y_positions = np.arange(len(growth_stage_dates))
        dates = list(growth_stage_dates.values())
        stages = list(growth_stage_dates.keys())
        
        ax_timeline.barh(y_positions, [1]*len(stages), left=[(d - self.sowing_date).days for d in dates], 
                        color=[stage_colors[stage] for stage in stages], alpha=0.7)
        
        ax_timeline.set_yticks(y_positions)
        ax_timeline.set_yticklabels(stages)
        ax_timeline.set_xlabel('Days After Sowing')
        ax_timeline.set_title('Wheat Growth Stage Timeline', fontsize=14, fontweight='bold')
        ax_timeline.grid(True, alpha=0.3)
        
        # Add date annotations
        for i, (stage, date) in enumerate(growth_stage_dates.items()):
            days = (date - self.sowing_date).days
            ax_timeline.text(days, i, f'\n{date.strftime("%m/%d")}', 
                            ha='center', va='center', fontsize=8)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        # plt.show()  # Removed to prevent blocking
        
        return fig
    
    def save_results(self, output_file='wheat_phenology_results.csv'):
        """Save daily NDVI, FVC, Ground Cover Percentage, and growth stage predictions to CSV"""
        # Add sowing and harvest dates to the output
        result_df = self.daily_ndvi.copy()
        result_df['Sowing_Date'] = self.sowing_date
        result_df['Harvest_Date'] = self.harvest_date
        
        # Reorder columns for better readability
        columns_order = ['Date', 'Days_After_Sowing', 'NDVI_Interpolated', 
                        'NDVI_Lower_CI', 'NDVI_Upper_CI', 'Growth_Stage', 
                        'Sowing_Date', 'Harvest_Date']
        
        # Add FVC columns if available
        if 'FVC_Interpolated' in result_df.columns:
            fvc_columns = ['FVC_Interpolated', 'FVC_Lower_CI', 'FVC_Upper_CI']
            columns_order = columns_order[:5] + fvc_columns + columns_order[5:]
        
        # Add ground cover percentage columns if available
        if 'Ground_Cover_Percentage' in result_df.columns:
            ground_cover_columns = ['Ground_Cover_Percentage', 'Ground_Cover_Lower_CI', 'Ground_Cover_Upper_CI']
            # Insert after FVC columns if they exist, otherwise after NDVI columns
            if 'FVC_Interpolated' in result_df.columns:
                insert_pos = 8  # After FVC columns
            else:
                insert_pos = 5  # After NDVI columns
            columns_order = columns_order[:insert_pos] + ground_cover_columns + columns_order[insert_pos:]
        
        result_df = result_df[columns_order]
        
        result_df.to_csv(output_file, index=False)
        print(f"Results saved to {output_file}")
        
        return result_df
    
    def generate_summary_report(self):
        """Generate a summary report of the analysis"""
        growth_stage_dates = self.estimate_growth_stages()
        
        print("\n" + "="*60)
        print("WHEAT PHENOLOGY ANALYSIS SUMMARY")
        print("="*60)
        print(f"Crop Period: {self.sowing_date.strftime('%d.%m.%Y')} to {self.harvest_date.strftime('%d.%m.%Y')}")
        print(f"Total Growing Season: {(self.harvest_date - self.sowing_date).days} days")
        print(f"Number of NDVI Observations: {len(self.ndvi_data)}")
        print(f"Peak NDVI: {self.daily_ndvi['NDVI_Interpolated'].max():.3f}")
        
        # Add FVC information if available
        if 'FVC_Interpolated' in self.daily_ndvi.columns:
            print(f"Peak FVC: {self.daily_ndvi['FVC_Interpolated'].max():.3f}")
            print(f"FVC Parameters - NDVI_soil: {self.fvc_params['ndvi_soil']:.3f}, NDVI_vegetation: {self.fvc_params['ndvi_vegetation']:.3f}")
        
        # Add ground cover percentage information if available
        if 'Ground_Cover_Percentage' in self.daily_ndvi.columns:
            print(f"Peak Ground Cover: {self.daily_ndvi['Ground_Cover_Percentage'].max():.1f}%")
        
        print("\nGROWTH STAGE TIMELINE:")
        print("-" * 40)
        for stage, date in growth_stage_dates.items():
            days_after_sowing = (date - self.sowing_date).days
            print(f"{stage:15s}: {date.strftime('%d.%m.%Y')} (Day {days_after_sowing:3d})")
        
        print("\nNDVI STATISTICS BY GROWTH STAGE:")
        print("-" * 40)
        for stage in self.growth_stages.keys():
            stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
            if not stage_data.empty:
                mean_ndvi = stage_data['NDVI_Interpolated'].mean()
                print(f"{stage:15s}: Mean NDVI = {mean_ndvi:.3f}")
        
        # Add FVC statistics if available
        if 'FVC_Interpolated' in self.daily_ndvi.columns:
            print("\nFVC STATISTICS BY GROWTH STAGE:")
            print("-" * 40)
            for stage in self.growth_stages.keys():
                stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
                if not stage_data.empty:
                    mean_fvc = stage_data['FVC_Interpolated'].mean()
                    print(f"{stage:15s}: Mean FVC = {mean_fvc:.3f}")
        
        # Add ground cover percentage statistics if available
        if 'Ground_Cover_Percentage' in self.daily_ndvi.columns:
            print("\nGROUND COVER PERCENTAGE STATISTICS BY GROWTH STAGE:")
            print("-" * 50)
            for stage in self.growth_stages.keys():
                stage_data = self.daily_ndvi[self.daily_ndvi['Growth_Stage'] == stage]
                if not stage_data.empty:
                    mean_ground_cover = stage_data['Ground_Cover_Percentage'].mean()
                    print(f"{stage:15s}: Mean Ground Cover = {mean_ground_cover:.1f}%")

    def compare_interpolation_methods(self, save_path='interpolation_comparison.png'):
        """Compare different interpolation methods"""
        methods = ['linear', 'cubic', 'physiological', 'sigmoid', 'balanced']
        results = {}
        
        for method in methods:
            analyzer_temp = WheatPhenologyAnalyzer(self.ndvi_file, 
                                                 self.sowing_date.strftime('%d.%m.%Y'),
                                                 self.harvest_date.strftime('%d.%m.%Y'))
            daily_ndvi = analyzer_temp.interpolate_ndvi(method=method)
            results[method] = daily_ndvi['NDVI_Interpolated'].values
        
        # Create comparison plot
        fig, ax = plt.subplots(figsize=(15, 8))
        
        date_range = pd.date_range(start=self.sowing_date, end=self.harvest_date, freq='D')
        
        for method, ndvi_values in results.items():
            ax.plot(date_range, ndvi_values, label=method, linewidth=2)
        
        # Plot original data points
        ax.scatter(self.ndvi_data['phenomenonTime'], self.ndvi_data['NDVI'], 
                  color='red', s=100, zorder=5, label='Observed NDVI')
        
        ax.set_xlabel('Date')
        ax.set_ylabel('NDVI')
        ax.set_title('Comparison of Interpolation Methods', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return results

def main():
    """Main function to run the wheat phenology analysis"""
    # Initialize analyzer
    analyzer = WheatPhenologyAnalyzer(
        ndvi_file='NDVI_ Treatment Parcel - 0-data-2025-07-04 15_11_14.csv',
        sowing_date='03.10.2023',
        harvest_date='30.07.2024'
    )
    
    # Estimate FVC parameters using seasonal analysis
    print("Estimating FVC parameters using seasonal analysis...")
    fvc_params = analyzer.estimate_fvc_parameters(method='seasonal')
    
    # Interpolate NDVI data (now includes FVC calculation)
    print("Interpolating NDVI data and calculating FVC using balanced approach...")
    daily_ndvi = analyzer.interpolate_ndvi(method='balanced')
    
    # Estimate growth stages
    print("Estimating growth stages...")
    growth_stages = analyzer.estimate_growth_stages()
    
    # Create visualization
    print("Creating visualization...")
    analyzer.create_visualization()
    
    # Compare interpolation methods
    print("Comparing interpolation methods...")
    analyzer.compare_interpolation_methods()
    
    # Save results
    print("Saving results...")
    results = analyzer.save_results()
    
    # Generate summary report
    analyzer.generate_summary_report()
    
    print("\nAnalysis complete! Check the generated files:")
    print("- wheat_phenology_results.csv: Daily NDVI, FVC, and growth stage predictions")
    print("- wheat_phenology_analysis.png: Visualization of the analysis")

if __name__ == "__main__":
    main() 