import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.optimize import curve_fit
from astropy.table import Table
from astropy.time import Time

class AnalyzeGuider:

    """
    Description:
        This class contains functions to analyze the Guider extensions in 
        L0 or 2D images (storing them as attributes) and functions to plot the results.

    Arguments:
        L0 - an L0 object (or a 2D object -- to be tested)

    Attributes:
        None so far
    """

    def __init__(self, L0, logger=None):
        self.L0 = L0
        self.pixel_scale = 0.056 # arcsec per pixel for the CRED-2 imager on the KPF FIU
        self.starname = self.L0['PRIMARY'].header['TARGNAME']
        self.ObsID = self.L0['PRIMARY'].header['OFNAME']
        self.guider_header = self.L0['GUIDER_AVG'].header
        if 'TTGAIN' in self.guider_header:
            self.tiptilt_gain = self.guider_header['TTGAIN']
        else:
            self.tiptilt_gain = 0.3 

        self.df_GUIDER = Table.read(self.L0, format='fits',hdu='guider_cube_origins').to_pandas()

        if logger:
            self.logger = logger
            self.logger.debug('AnalyzeGuider class constructor')
        else:
            self.logger = None
            print('---->AnalyzeGuider class constructor')


    def measure_seeing(self):

        """
        Compute the seeing from a stacked guider image.

        Args:
            None

        Attributes:
            guider_image - stacked guider image
            image_fit - image of the Moffat function fit of the guider image; 
                        this has the same dimensions as guider_image
            amplitude - amplitude of the fitted Moffat function
            seeing_550nm - seeing value scaled with wavelength^(1/5)
            seeing - seeing value at the guide camera wavelengths (950-1200 nm);
                     equal to the alpha parameter of the fitted Moffat function
            beta - beta parameter of the fitted Moffat function
            x0 - x-coordinate of the centroid of the fitted Moffat function 
            y0 - x-coordinate of the centroid of the fitted Moffat function 

        Returns:
            None
        """
        
        self.guider_image = self.L0['GUIDER_AVG'].data - np.median(self.L0['GUIDER_AVG'].data)

        def moffat_2D(xy, amplitude, x0, y0, alpha, beta):
            x, y = xy
            return amplitude * (1 + ((x - x0) ** 2 + (y - y0) ** 2) / alpha ** 2) ** -beta

        x = np.arange(self.guider_image.shape[1])
        y = np.arange(self.guider_image.shape[0])
        X, Y = np.meshgrid(x, y)
        x_flat = X.flatten()
        y_flat = Y.flatten()
        image_data_flat = self.guider_image.flatten()
        p0 = [1, self.guider_header['CRPIX1'], self.guider_header['CRPIX2'], 5/0.056, 2.5]  # Initial guess for the parameters
        #p0 = [1, self.guider_image.shape[1] / 2, self.guider_image.shape[0] / 2, 2/0.056, 2]  # Initial guess for the parameters
        
        #self.guider_image = guider_im
        try:
            popt, pcov = curve_fit(moffat_2D, (x_flat, y_flat), image_data_flat, p0=p0)
            amplitude_fit, x0_fit, y0_fit, alpha_fit, beta_fit = popt
            alpha_fit = abs(alpha_fit)
            self.good_fit = True
            self.image_fit = moffat_2D((X, Y), amplitude_fit, x0_fit, y0_fit, alpha_fit, beta_fit)
            self.amplitude = amplitude_fit
            self.seeing = alpha_fit
            self.seeing_550nm = self.seeing*(((1200+950)/2)/550)**0.2  # seeing scales with wavelength^0.2
            self.beta = beta_fit
            self.x0 = x0_fit
            self.y0 = y0_fit
        except:
            self.good_fit = False
        
        #resid_im = guider_im - image_fit


    def plot_guider_image(self, fig_path=None, show_plot=False):

        """
        Generate a three-panel plot of the guider image (full view), the zoomed-in 
        guider image, and residuals of the guider image with a fitted Moffat function. 
        Note that the function AnalyzeGuider.measure_seeing must be run first.

        Args:
            fig_path (string) - set to the path for a SNR vs. wavelength file 
                to be generated.
            show_plot (boolean) - show the plot in the current environment.

        Returns:
            PNG plot in fig_path or shows the plot it the current environment 
            (e.g., in a Jupyter Notebook).

        """

        # Plot the original image and residuals
        guider_im_zoom = self.guider_image[255-38:255+38, 320-38:320+38]
        if self.good_fit:
            resid_im = self.guider_image - self.image_fit
            resid_im_zoom = resid_im[255-38:255+38, 320-38:320+38]
        else:
            resid_im_zoom = 0*self.guider_image[255-38:255+38, 320-38:320+38]

        fig, axs = plt.subplots(1, 3, figsize=(15, 5), tight_layout=True)

        # Left panel - full image
        im1 = axs[0].imshow(self.guider_image, cmap='viridis', origin='lower', vmin=0, vmax=np.percentile(guider_im_zoom,99.9))
        axs[1].set_aspect(640/512)
        image_size_pixels = self.guider_image.shape
        image_size_arcsec = (image_size_pixels[1] * self.pixel_scale, image_size_pixels[0] * self.pixel_scale)
        x_tick_locator = ticker.MultipleLocator(5/(self.pixel_scale-0.001))  # Set tick every 5 arcsec
        axs[0].xaxis.set_major_locator(x_tick_locator)
        y_tick_locator = ticker.MultipleLocator(5/(self.pixel_scale-0.001))  # Set tick every 5 arcsec
        axs[0].yaxis.set_major_locator(y_tick_locator)
        xticks = axs[0].get_xticks()
        yticks = axs[0].get_yticks()
        axs[0].set_xticklabels([f'{int(x * self.pixel_scale)}' for x in xticks])
        axs[0].set_yticklabels([f'{int(y * self.pixel_scale)}' for y in yticks])
        axs[0].set_xlabel('Arcseconds', fontsize=12)
        axs[0].set_ylabel('Arcseconds', fontsize=12)
        title = str(self.ObsID)+' - ' + self.starname 
        if self.good_fit:
            title = title + "\n seeing: " + f"{(self.seeing*self.pixel_scale):.2f}" + '" (z+J)'+ r' $\rightarrow$ ' +f"{(self.seeing_550nm*self.pixel_scale):.2f}" + '" (V, scaled)'
        axs[0].set_title(title, fontsize=12)
        axs[0].grid(True, linestyle='solid', linewidth=0.5, alpha=0.5)
        #cbar1 = plt.colorbar(im1, ax=axs[0], shrink=0.5)
        #cbar1.set_label('Intensity', fontsize=12)

        # Middle panel - zoomed image
        im2 = axs[1].imshow(guider_im_zoom, cmap='viridis', origin='lower', vmin=0, vmax=np.percentile(guider_im_zoom,99.9))
        axs[1].set_aspect('equal')
        image_size_pixels = guider_im_zoom.shape
        image_size_arcsec = (image_size_pixels[1] * self.pixel_scale, image_size_pixels[0] * self.pixel_scale)
        x_tick_locator = ticker.MultipleLocator(0.5/(self.pixel_scale-0.001))  # Set tick every 0.5 arcsec
        axs[1].xaxis.set_major_locator(x_tick_locator)
        y_tick_locator = ticker.MultipleLocator(0.5/(self.pixel_scale-0.001))  # Set tick every 0.5 arcsec
        axs[1].yaxis.set_major_locator(y_tick_locator)
        xticks = axs[1].get_xticks()
        yticks = axs[1].get_yticks()
        axs[1].set_xticklabels([f'{int(x * self.pixel_scale*10)/10}' for x in xticks])
        axs[1].set_yticklabels([f'{int(y * self.pixel_scale*10)/10}' for y in yticks])
        axs[1].set_xlabel('Arcseconds', fontsize=12)
        axs[1].set_ylabel('Arcseconds', fontsize=12)
        axs[1].set_title('Guider Image (zoomed in)', fontsize=12)
        axs[1].grid(True, linestyle='solid', linewidth=0.5, alpha=0.5)
        cbar2 = plt.colorbar(im2, ax=axs[1], shrink=0.7)
        #cbar2.set_label('Intensity', fontsize=12)

        # Right panel - zoomed image of residuals to model
        im2 = axs[2].imshow(resid_im_zoom, cmap='viridis', origin='lower', vmin=0, vmax=np.percentile(guider_im_zoom,99.9))
        image_size_pixels = guider_im_zoom.shape
        image_size_arcsec = (image_size_pixels[1] * self.pixel_scale, image_size_pixels[0] * self.pixel_scale)
        x_tick_locator = ticker.MultipleLocator(0.5/(self.pixel_scale-0.001))  # Set tick every 0.5 arcsec
        axs[2].xaxis.set_major_locator(x_tick_locator)
        y_tick_locator = ticker.MultipleLocator(0.5/(self.pixel_scale-0.001))  # Set tick every 0.5 arcsec
        axs[2].yaxis.set_major_locator(y_tick_locator)
        xticks = axs[2].get_xticks()
        yticks = axs[2].get_yticks()
        axs[2].set_xticklabels([f'{int(x * self.pixel_scale*10)/10}' for x in xticks])
        axs[2].set_yticklabels([f'{int(y * self.pixel_scale*10)/10}' for y in yticks])
        axs[2].set_xlabel('Arcseconds', fontsize=12)
        axs[2].set_ylabel('Arcseconds', fontsize=12)
        if self.good_fit:
            title = 'Residuals to Moffat Function Model'
        else:
            title = 'Unsuccessful fit to Moffat Function Model'
        axs[2].set_title(title, fontsize=12)
        axs[2].grid(True, linestyle='solid', linewidth=0.5, alpha=0.5)
        cbar3 = plt.colorbar(im2, ax=axs[2], shrink=0.7)
        #cbar3.set_label('Intensity', fontsize=12)

            
        # Display the plot
        if fig_path != None:
            plt.savefig(fig_path, dpi=288, facecolor='w')
        if show_plot == True:
            plt.show()
        plt.close()


    def plot_guider_error_time_series(self, fig_path=None, show_plot=False):

        """
        Generate a two-panel plot of the guider time series errors as 1) a time series 
        and 2) as a 2-D histogram.

        Args:
            fig_path (string) - set to the path for a SNR vs. wavelength file 
                to be generated.
            show_plot (boolean) - show the plot in the current environment.

        Returns:
            PNG plot in fig_path or shows the plot it the current environment 
            (e.g., in a Jupyter Notebook).

        """
        
        if np.sqrt(self.df_GUIDER.shape[0]) < 60:
            hist_bins = 25
        else:
            hist_bins = 40
        
        # Create the figure and subplots
        fig, axes = plt.subplots(1, 2, figsize=(16, 4), gridspec_kw={'width_ratios': [2, 1]})
        plt.style.use('seaborn-whitegrid')

        x_mas = self.df_GUIDER.command_x/self.tiptilt_gain*self.pixel_scale*1000
        y_mas = self.df_GUIDER.command_y/self.tiptilt_gain*self.pixel_scale*1000
        r_mas = (x_mas**2+y_mas**2)**0.5

        # Plot the data
        im1 = axes[1].hist2d(x_mas, y_mas, bins=hist_bins, cmap='viridis')
        axes[1].set_title(r'Guiding Errors - $\langle\,\left|\mathrm{r}\right|\,\rangle$ = ' + f'{int(np.average(np.absolute(r_mas))*10)/10}'+' mas', fontsize=14)
        axes[1].set_xlabel('x (mas)', fontsize=14)
        axes[1].set_ylabel('y (mas)', fontsize=14)
        axes[1].grid(True, linestyle='solid', linewidth=0.5, alpha=0.5)
        cbar = plt.colorbar(im1[3])
        cbar.set_label('Samples', fontsize=12)

        axes[0].plot(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp), x_mas, color='royalblue')
        axes[0].plot(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp), y_mas, color='orange')
        axes[0].set_title("Guiding Error Time Series: " + str(self.ObsID)+' - ' + self.starname, fontsize=14)
        axes[0].set_xlabel("Time (sec)", fontsize=14)
        axes[0].set_ylabel("Guiding Error (mas)", fontsize=14)
        axes[0].legend([r'$\langle\,\left|\mathrm{x}\right|\,\rangle$ = ' + f'{int(np.average(np.absolute(x_mas))*10)/10}' + ' mas', 
                        r'$\langle\,\left|\mathrm{y}\right|\,\rangle$ = ' + f'{int(np.average(np.absolute(y_mas))*10)/10}' + ' mas'], fontsize=12, loc='best') 

        # Set the font size of tick mark labels
        axes[0].tick_params(axis='both', which='major', labelsize=14)
        axes[1].tick_params(axis='both', which='major', labelsize=14)

        # Display the plot
        if fig_path != None:
            plt.savefig(fig_path, dpi=144, facecolor='w')
        if show_plot == True:
            plt.show()
        plt.close()

        
    def plot_guider_flux_time_series(self, fig_path=None, show_plot=False):

        """
        Generate a plot of the guider flux time series errors.
        
        To-do: compute the flux in a octagonal aperture centered on the guiding origin

        Args:
            fig_path (string) - set to the path for a SNR vs. wavelength file 
                to be generated.
            show_plot (boolean) - show the plot in the current environment.

        Returns:
            PNG plot in fig_path or shows the plot it the current environment 
            (e.g., in a Jupyter Notebook).

        """

        # Construct plots
        plt.style.use('seaborn-whitegrid')
        plt.figure(figsize=(8, 4), tight_layout=True)
        plt.plot(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp), self.df_GUIDER.object1_flux/np.nanpercentile(self.df_GUIDER.object1_flux, 95), color='royalblue')
        #plt.plot(time, int_SCI_flux / ((847+4.8/2)-(450.1-0.4/2)) / tdur_sec / max(int_SCI_flux / ((847+4.8/2)-(450.1-0.4/2)) / tdur_sec), marker='o', color='k')
        plt.title("Guiding Error Time Series: " + str(self.ObsID)+' - ' + self.starname, fontsize=14)
        plt.xlabel("Seconds since " + str(self.guider_header['DATE-BEG']), fontsize=14)
        plt.ylabel("Flux (fractional)", fontsize=14)
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
        plt.xlim(min(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp)), max(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp)))
        plt.legend(['Guider Flux', 'Exposure Meter Flux'], fontsize=12, loc='best') 

        # Display the plot
        if fig_path != None:
            plt.savefig(fig_path, dpi=144, facecolor='w')
        if show_plot == True:
            plt.show()
        plt.close()


    def plot_guider_fwhm_time_series(self, fig_path=None, show_plot=False):

        """
        Generate a plot of the guider FWHM time series errors.

        Args:
            fig_path (string) - set to the path for a SNR vs. wavelength file 
                to be generated.
            show_plot (boolean) - show the plot in the current environment.

        Returns:
            PNG plot in fig_path or shows the plot it the current environment 
            (e.g., in a Jupyter Notebook).

        """

        # Make FWHM time series
        fwhm = (self.df_GUIDER.object1_a**2 + self.df_GUIDER.object1_b**2)**0.5 / self.pixel_scale * (2*(2*np.log(2))**0.5)

        # Construct plots
        plt.style.use('seaborn-whitegrid')
        plt.figure(figsize=(8, 4), tight_layout=True)
        plt.plot(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp), fwhm, color='royalblue')
        plt.title("Guider FWHM Time Series: " + str(self.ObsID)+' - ' + self.starname, fontsize=14)
        plt.xlabel("Seconds since " + str(self.guider_header['DATE-BEG']), fontsize=14)
        plt.ylabel("FWHM (mas)", fontsize=14)
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
        plt.xlim(min(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp)), max(self.df_GUIDER.timestamp-min(self.df_GUIDER.timestamp)))
        plt.legend(['Guider FWHM'], fontsize=12, loc='best') 

        # Display the plot
        if fig_path != None:
            plt.savefig(fig_path, dpi=144, facecolor='w')
        if show_plot == True:
            plt.show()
        plt.close()
