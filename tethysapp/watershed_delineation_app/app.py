from tethys_sdk.base import TethysAppBase, url_map_maker


class WatershedDelineationApp(TethysAppBase):
    """
    Tethys app class for Watershed Delineation App.
    """

    name = 'Watershed Delineation for Dominican Republic'
    index = 'watershed_delineation_app:home'
    icon = 'watershed_delineation_app/images/watershedicon.png'
    package = 'watershed_delineation_app'
    root_url = 'watershed-delineation-app'
    color = '#27ae60'
    description = 'This app allows you to perform watershed delineation in Dominican Republic Country.'
    tags = ''
    enable_feedback = False
    feedback_emails = ['xhqiao89@gmail.com']

    def url_maps(self):
        """
        Add controllers
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (
            UrlMap(
                name='home',
                url='watershed-delineation-app',
                controller='watershed_delineation_app.controllers.home'
            ),
            UrlMap(name='run',
                   url='watershed-delineation-app/run',
                   controller='watershed_delineation_app.controllers.run_wd')
        )

        return url_maps
