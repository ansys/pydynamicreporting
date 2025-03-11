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

import json
import os
import sys
from typing import Optional
import warnings
import webbrowser

from ansys.dynamicreporting.core.adr_utils import build_query_url, in_ipynb
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

    def visualize(self, new_tab: bool = False, filter: str = "", item_filter: str = "") -> None:
        """
        Render the report.

        Parameters
        ----------
        new_tab : bool, optional
            Whether to render the report in a new tab if the current environment
            is a Jupyter notebook. The default is ``False``, in which case the
            report is rendered in the current location. If the environment is
            not a Jupyter notebook, the report is always rendered in a new tab.
        filter : str, optional
            DEPRECATED. Use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.

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
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
        if in_ipynb() and not new_tab:  # pragma: no cover
            iframe = self.get_iframe()
            if iframe is None:  # pragma: no cover
                self.service.logger.error("Error: can not obtain IFrame for report")
            else:
                display(iframe)
        else:
            url = self.get_url(item_filter=item_filter)
            if url == "":  # pragma: no cover
                self.service.logger.error("Error: could not obtain url for report")
            else:
                webbrowser.open_new(url)

    def get_url(self, filter: str = "", item_filter: str = "") -> str:
        """
        Get the URL corresponding to the report.

        Parameters
        ----------
        filter : str, optional
            DEPRECATED. Use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.

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
            print("No connection to any report")
            return ""
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
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
        url += build_query_url(logger=self.service.logger, item_filter=item_filter)
        return url

    def get_guid(self) -> str:
        """
        Get the guid corresponding to the report.

        Returns
        -------
        str
            guid corresponding to the report. If no guid exists, an empty string is returned.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = 'Top report')
            report_url = my_report.get_guid()
        """
        guid = ""
        if self.service is None:  # pragma: no cover
            self.service.logger.error("No connection to any report")
            return guid
        if self.service.serverobj is None or self.service.url is None:  # pragma: no cover
            self.service.logger.error("No connection to any server")
            return guid
        if self.report:
            guid = self.report.guid
        else:  # pragma: no cover
            success = self.__find_report_obj__()
            if success:
                guid = self.report.guid
            else:
                self.service.logger.error("Error: can not obtain the report guid")

        return guid

    def get_report_script(self) -> str:
        """
        A block of JavaScript script to define the web component for report fetching.
        Note that the function return a block of string that stands for JavaScript codes
        and need to be wrapped in a <script>...</script> HTML tag.

        .. note::

            This feature has been deprecated as of 2025 R2. Refer to the ``adr_offline_report_src.js``
            file in the ``django/utils/remote/adr_offline_report_src/`` directory, from the latest ADR
            installation. The new web component ``<adr-offline-report></adr-offline-report>`` supports
            report embed and style overwrites generated from both server and serverless ADR.


        Returns
        -------
        str
            JavaScript code to define the report fetching web component (as a block of string)
            that will get embedded in the HTML page

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = 'Top report')
            my_report.get_report_script()
        """
        # helper fn to load <script> <link> & <style> on report fetch
        loadScript = """
            loadDependencies(tgtList, createTgt="", appendTgt = ""){
                const promiseQueue = [];
                for(let tgt of tgtList){
                    promiseQueue.push(
                        (function(){

                            return new Promise((resolve, reject)=>{
                                let ele = document.createElement(createTgt);

                                ele.addEventListener("load", () => {
                                    return resolve(true)
                                }, {once:true});

                                if(ele.tagName === "SCRIPT"){
                                    tgt.src ?
                                        ele.setAttribute("src", `${tgt.getAttribute("src")}`)
                                        :
                                        ele.innerHTML = tgt.innerHTML;
                                    ele.type = "text/javascript";
                                    ele.async = false;

                                }else if(ele.tagName === "LINK"){
                                    ele.type = "text/css";
                                    ele.rel = tgt.rel;
                                    ele.setAttribute("href", `${tgt.getAttribute("href")}`);
                                }else{
                                    ele.innerHTML = tgt.innerHTML;
                                }

                                if(appendTgt){
                                    document.querySelector(appendTgt).appendChild(ele);
                                }

                                if(tgt.tagName === "STYLE" || !tgt.src){
                                    resolve(true)
                                }

                                ele.addEventListener("error", () => {
                                    return reject(new Error(`${this} failed to load.`))
                                }, {once:true})

                            })

                        })()
                    )
                }

                return Promise.all(promiseQueue)
            }
        """
        # helper fn to remove duplicated <script> on report fetch
        removeDuplicates = """
            removeScript(root){
                return new Promise((resolve, reject)=>{
                    try{
                        const scriptList = root.querySelectorAll(" script")
                        for(let i = 0; i < scriptList.length; i++){
                            // loop thru the script list and remove <script> one by one
                            scriptList[i].remove()
                            if(i === scriptList.length-1){
                                // once reach and remove the final <script>, then resolve
                                resolve(true)
                            }
                        }
                    }catch(err){
                        reject(err)
                    }
                })
            }
        """
        # report fetch main fn
        reportFetch = """
            reportFetch(prefix, guid, query){
                return new Promise((resolve, reject)=>{
                    fetch(`/${prefix}/${guid}/${query}`)
                    .then(res=>{
                        // get the html text first
                        return res.text();
                    })
                    .then(report=>{
                        // convert the html text to DOM object (for querySelector... later)
                        return new DOMParser().parseFromString(report, 'text/html')
                    })
                    .then(reportHTML=>{
                        // get the <adr-report-root>'s children & back_to_top button
                        // since "return_to_top btn" is not inside <adr-report-root>
                        const reportRoot = reportHTML.querySelector('adr-report-root');
                        const returnToTop = reportHTML.querySelector('a#return_to_top');

                        // async loaded script/link/style (append and load BEFORE report body mounted in the DOM)
                        const asyncLinks = reportHTML.querySelectorAll('head>link');
                        const asyncStyles = reportHTML.querySelectorAll('head>style, body>style');

                        // :not(...) in querySelector is not support in Chrome v87 (Qt Web Engine)
                        // thus, use .filter() for backward compatibility

                        // Store all <script> with src path that are not base/report_item/report_display.js
                        // under <head> & <body>, included nested <script> inside <adr-report-root> as a variable
                        // (*Note base/report_item/report_display.js depend on report HTML elements, so need to
                        //  append AFTER report body is mounted)
                        const asyncScripts = [...reportHTML.querySelectorAll(`head>script[src], body script[src]`)].filter(el=>{
                            return !el.src.endsWith('base.js') &&
                                !el.src.endsWith('report_item.js') &&
                                !el.src.endsWith('report_display.js')
                        });
                        const asyncScriptsInLine = [...reportHTML.querySelectorAll('head>script')].filter(el=>!el.src);

                        // defer loaded script (append and load AFTER report body mounted in the DOM)
                        // Store all inline <script> & base/report_item/report_display.js under <body>,
                        // included nested script inside <adr-report-root> as a variable.
                        // (we'll remove these scripts later and then append/load/run all over again
                        const deferScripts = [...reportHTML.querySelectorAll('body script')].filter(el=>{
                            return !el.src ||
                                el.src.endsWith('base.js') ||
                                el.src.endsWith('report_item.js') ||
                                el.src.endsWith('report_display.js');
                        });

                        // promise chain: ORDER MATTERS!!
                        Promise.all([
                            // load async dependencies first
                            this.loadDependencies(asyncLinks, 'link', 'head'),
                            this.loadDependencies(asyncStyles, 'style', 'head'),
                            this.loadDependencies(asyncScripts, 'script', 'head')
                        ]).then(()=>{
                            // after resolved, then load async inline script
                            // (*Order matters!! as inline script may depend on the async <script> with src)
                            return this.loadDependencies(asyncScriptsInLine, 'script', 'head')

                        }).then(()=>{
                            // Start handling the report contents...
                            return new Promise((resolve, reject)=>{
                                // append core report <section>
                                try{
                                    // remove all nested <script> first under <adr-report-root> as we'll append all these
                                    // <script> later, load, and run again, thus, need to clean up the duplicated scripts
                                    this.removeScript(reportRoot)
                                        // Once remove the script then append the report body (Now no nested <script>)
                                        .then(()=>this.innerHTML = reportRoot.innerHTML + returnToTop.outerHTML)
                                        .then(()=>{
                                            // once report children > 0, namely...done appending then resolve and return
                                            // the scripts stored initially as a variable (deferScripts) for append & load
                                            if(this.childElementCount > 0){
                                                return resolve(deferScripts)
                                            }
                                        })
                                }catch(err){
                                    reject(err)
                                }
                            })

                        }).then(deferScripts => {
                            // append & load all nested <script> inside <adr-report-root>
                            return this.loadDependencies(deferScripts, 'script', 'adr-report')
                        })

                    })
                    .catch(function (err) {
                        // There was an error
                        console.warn('Something went wrong.', err);
                        reject(err);
                    });
                })
            }
        """
        # component logic define
        component_logic = f"""
            class ReportFetchComponent extends HTMLElement {{
                constructor() {{
                    super();
                }}

                {loadScript}
                {removeDuplicates}
                {reportFetch}

                connectedCallback(){{
                    const prefix = this.getAttribute('prefix') || "";
                    const guid = this.getAttribute('guid') || "";
                    const query = this.getAttribute('query').replaceAll("|", "%7C").replaceAll(";", "%3B") || "";
                    const reportPath = this.getAttribute('reportURL') || "";
                    const width = this.getAttribute('width') || "";
                    const height = this.getAttribute('height') || "";

                    if(prefix && guid){{
                        // fetch report
                        return this.reportFetch(prefix, guid, query);
                    }}

                    if(reportPath){{
                        // use <iframe> instead
                        const iframeEle = document.createElement('iframe');
                        iframeEle.src = reportPath;
                        iframeEle.width = width;
                        iframeEle.height = height;
                        return this.appendChild(iframeEle);
                    }}
                }}
            }}

            customElements.define("adr-report", ReportFetchComponent);
        """  # noqa
        return component_logic

    def get_report_component(
        self,
        prefix: str = "",
        filter: str = "",
        style_path: str = "",
        width: int = 1000,
        height: int = 800,
        item_filter: str = "",
    ) -> str:
        """
        A HTML code of the web component for report fetching. By default, the web
        component uses iframe to embed the report. If users have provided additional
        configuration settings on their application server or on another proxy server,
        the web component will use fetch API to embed the report directly in the
        application.

        .. note::

            This feature has been deprecated as of 2025 R., Refer to the ``adr_offline_report_src.js``
            file in the ``django/utils/remote/adr_offline_report_src/`` directory, from the latest ADR
            installation. The new web component ``<adr-offline-report></adr-offline-report>`` supports
            report embed and style overwrites generated from both server and serverless ADR.


        Parameters
        ----------
        prefix : str, optional
            A user defined key in the server to reroute and fetch the report from ADR server. If not provided,
            the web component will use the default iframe to embed the report in the application.
        filter : str, optional
            DEPRECATED: use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.
        style_path: str, optional
            The hosting app's stylesheet path. The default is ``""``. The syntax is used to overwrite report
            styling using an external CSS file.
        width : int, optional
            Width of the iframe if the web component uses <iframe> to embed report. The default is ``1000``.
        height : int, optional
            Height of the iframe if the web component uses <iframe> to embed report. The default is ``800``.

        Returns
        -------
        str
            The web component HTML code (as string) that will get embedded in the HTML page

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = 'Top report')
            my_report.get_report_component()
        """
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
        # fetch method using predefined prefix rules in the proxy server OR using traditional <iframe>
        # add host-style-path attribute if specified (can only work when prefix is provided)
        host_style_path = f'host-style-path="{style_path}"' if style_path else ""
        fetch_method = (
            f'prefix="{prefix}" guid="{self.get_guid()}" query="{item_filter}" {host_style_path}'
            if prefix
            else f'reportURL="{self.get_url()}" width="{width}" height="{height}"'
        )
        component = f"<adr-report {fetch_method}></adr-report>"
        return component

    def get_iframe(
        self, width: int = 1000, height: int = 800, filter: str = "", item_filter: str = ""
    ):
        """
        Get the iframe object corresponding to the report.

        Parameters
        ----------
        width : int, optional
            Width of the iframe object. The default is ``1000``.
        height : int, optional
            Height of the iframe object. The default is ``800``.
        filter : str, optional
            DEPRECATED. Use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query Expressions in the documentation for Ansys Dynamic Reporting.

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
            my_report = adr_service.get_report(report_name = "My Top Report")
            report_iframe = my_report.get_iframe()
        """
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
        if "IPython.display" in sys.modules:
            url = self.get_url(item_filter=item_filter)
            iframe = IFrame(src=url, width=width, height=height)
        else:
            iframe = None
        return iframe

    def export_pdf(
        self,
        file_name: str = "",
        query_params: dict | None = None,
        item_filter: str | None = None,
        page: list | None = None,
        delay: int | None = None,
    ) -> bool:
        """
        Export report as PDF. Currently works only with a local ADR installation, and
        not a docker image.

        Parameters
        ----------
        file_name : str
            Path and filename for the PDF file to export.
        query_params : dict, optional
            Dictionary for parameters to apply to report template. Default: None
        item_filter: str, optional
            String corresponding to query to run on the database items before rendering the report.
            Default: None
        page : list, optional
            List of integers that represents the size of the exported pdf. Default: None, which
            corresponds to A4 size
        delay : int, optional
            Seconds to delay the start of the pdf export operation. Default: None, which
            corresponds to no delay

        Returns
        -------
        bool
            Success status of the PDF export: True if it worked, False otherwise

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = "My Top Report")
            succ = my_report.export_pdf(file_name=r'D:\\tmp\\myreport.pdf', query_params = {"colormode": "dark"})
            succ2 = my_report.export_pdf(filename=r'D:\\tmp\\onlyimages.pdf', item_filter = 'A|i_type|cont|image;')
        """
        success = False  # pragma: no cover
        if self.service is None:  # pragma: no cover
            self.service.logger.error("No connection to any report")
            return ""
        if self.service.serverobj is None:  # pragma: no cover
            self.service.logger.error("No connection to any server")
            return ""
        try:  # pragma: no cover
            if query_params is None:
                query_params = {}
            self.service.serverobj.export_report_as_pdf(
                report_guid=self.report.guid,
                file_name=file_name,
                query=query_params,
                item_filter=item_filter,
                page=page,
                parent=None,
                delay=delay,
                exec_basis=self.service._ansys_installation,
                ansys_version=self.service._ansys_version,
            )
            success = True
        except Exception as e:  # pragma: no cover
            self.service.logger.error(f"Can not export pdf report: {str(e)}")
        return success

    def export_html(
        self,
        directory_name: str = "",
        query_params: dict | None = None,
        item_filter: str | None = None,
        filename: str | None = "index.html",
        no_inline_files: bool | None = False,
    ) -> bool:
        """
        Export report as static HTML.

        Parameters
        ----------
        directory_name : str
            Path for the HTML export directory
        query_params : dict, optional
            Dictionary for parameters to apply to report template. Default: None
        item_filter: str, optional
            String corresponding to query to run on the database items before rendering the report.
            Default: None
        filename : str, optional
            Filename for the exported static HTML file. Default: index.html
        no_inline_files : bool, optional
            If True, the information is exported as stand alone files instead of in line content
            in the static HTML. Default: False

        Returns
        -------
        bool
            Success status of the HTML export: True if it worked, False otherwise

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_report = adr_service.get_report(report_name = "My Top Report")
            succ = my_report.export_html(directory_name = r'D:\\tmp', query_params={"colormode": "dark"})
            succ2 = my_report.export_html(filename=r'D:\\tmp\\onlyimages.pdf', item_filter = 'A|i_type|cont|image;')
        """
        success = False
        if self.service is None:  # pragma: no cover
            self.service.logger.error("No connection to any report")
            return ""
        if self.service.serverobj is None:  # pragma: no cover
            self.service.logger.error("No connection to any server")
            return ""
        try:
            if query_params is None:
                query_params = {}
            self.service.serverobj.export_report_as_html(
                report_guid=self.report.guid,
                directory_name=directory_name,
                query=query_params,
                item_filter=item_filter,
                filename=filename,
                no_inline_files=no_inline_files,
                ansys_version=self.service._ansys_version,
            )
            success = True
        except Exception as e:  # pragma: no cover
            self.service.logger.error(f"Can not export static HTML report: {str(e)}")
        return success

    def export_json(self, json_file_path: str) -> None:
        """
        Export this report to a JSON-formatted file.

        Parameters
        ----------
            json_file_path : str
                Path of the JSON file to be exported to.

        Returns
        -------
            None.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr

            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020', username = "admin", password = "mypassword")
            report = adr_service.get_report(report_name="my_report_name")
            report.export_json(r'C:\\tmp\\my_json_file.json')
        """
        try:
            self.service.serverobj.store_json(self.report.guid, json_file_path)
        except Exception as e:
            self.service.logger.error(
                f"Exporting to JSON terminated for report: {self.report_name}\n"
                f"Error details: {e}"
            )
