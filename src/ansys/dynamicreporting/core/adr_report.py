"""
Report module.

Module to handle Report instances.

A top-level report from an Ansys Dynamic Reporting database can be represented
as a ``Report`` instance. This class allows for easy creation and
manipulation of such objects.

Examples
--------
::

    import ansys.dynamicreporting.core as adr
    adr_service = adr.Service()
    ret = adr_service.connect()
    my_report = adr_service.get_report(report_name = "My First Report")
    my_report.visualize()
"""
import sys
import webbrowser

from ansys.dynamicreporting.core.adr_utils import in_ipynb
from ansys.dynamicreporting.core.utils import report_objects

try:
    from IPython.display import IFrame
except ImportError:
    pass


# Generate the report object for the database
class Report:
    """
    Provides for generating the ``Report`` object for the database.

    Parameters
    ----------
    service : ansys.dynamicreporting.core.Service, optional
        Ansys Dynamic Reporting object that provides the connection to the database.
        The default is ``None``.
    report_name : str, optional
        Name of the report object in the database. The default is ``default``.
    report_obj : str, optional
        TemplateREST object from low-level ADR API. Do not modify.
    """

    def __init__(self, service=None, report_name="default", report_obj=None):
        self.report_name = report_name
        self.service = service
        if report_obj is None:
            self.__find_report_obj__()
        else:
            self.report = report_obj

    def __find_report_obj__(self) -> bool:
        """
        Find the TemplateREST object corresponding to the Report object and set
        self.report to it.

        Returns
        -------
        bool
            ``True`` if a ``TemplateREST`` object was found and assigned to ``self.report``,
            ``False`` otherwise.
        """
        success = False
        all_reports = self.service.serverobj.get_objects(objtype=report_objects.TemplateREST)
        report_objs = [x for x in all_reports if x.name == self.report_name]
        if len(report_objs) > 0:
            all_top_levels = [x for x in report_objs if x.parent is None]
            if len(all_top_levels) > 0:
                self.report = all_top_levels[0]
                success = True
        return success

    def visualize(self, new_tab: bool = False) -> None:
        """
        Render the report.

        Parameters
        ----------
        new_tab : bool, optional
            Whether to render the report in a new tab if the current environment
            is a Jupyter notebook. The default is ``False``, in which case the
            report is rendered in the current location. If the environment is
            not a Jupyter notebook, the report is always rendered in a new tab.

        Returns
        -------
        Report
            Rendered report.

        Examples
        --------
        Render a report in a new tab.
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = "My First Report")
            my_report.visualize(new_tab = True)
        """
        if in_ipynb() and not new_tab:  # pragma: no cover
            iframe = self.get_iframe()
            if iframe is None:  # pragma: no cover
                self.service.logger.error("Error: can not obtain IFrame for report")
            else:
                display(iframe)
        else:
            url = self.get_url()
            if url == "":  # pragma: no cover
                self.service.logger.error("Error: could not obtain url for report")
            else:
                webbrowser.open_new(url)

    def get_url(self) -> str:
        """
        Get the URL corresponding to the report.

        Returns
        -------
        str
            URL corresponding to the report. If no URL exists, an empty string is returned.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = 'Top report')
            report_url = my_report.get_url()
        """
        if self.service is None:  # pragma: no cover
            self.service.logger.error("No connection to any report")
            return ""
        if self.service.serverobj is None:  # pragma: no cover
            self.service.logger.error("No connection to any server")
            return ""
        if self.service.url is None:
            self.service.logger.error("No connection to any server")
            return ""
        url = self.service.url + "/reports/report_display/?"
        if self.report:
            url += "view=" + self.report.guid + "&"
        else:  # pragma: no cover
            success = self.__find_report_obj__()
            if success:
                url += "view=" + self.report.guid + "&"
            else:
                self.service.logger.error(
                    "Can not identify TemplateREST obj corresponding to " "the report"
                )
                return ""
        url += "usemenus=off"
        return url

    def get_iframe(self, width: int = 1000, height: int = 800):
        """
        Get the iframe object corresponding to the report.

        Parameters
        ----------
        width : int, optional
            Width of the iframe object. The default is ``1000``.
        height : int, optional
            Height of the iframe object. The default is ``800``.

        Returns
        -------
        iframe
            iframe object corresponding to the report. If no iframe can be generated,
            ``None`` is returned.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = "My Top Report"
            report_iframe = my_report.get_iframe()
        """
        if "IPython.display" in sys.modules:
            url = self.get_url()
            iframe = IFrame(src=url, width=width, height=height)
        else:
            iframe = None
        return iframe
