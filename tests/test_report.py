import os

import pytest

from ansys.dynamicreporting.core import Report, Service
from ansys.dynamicreporting.core.utils import report_remote_server


@pytest.mark.ado_test
def test_geturl_report(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    url = my_report.get_url()
    assert "http:" in url


@pytest.mark.ado_test
def test_geturl_report_with_filter(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    url = my_report.get_url(filter='"A|b_type|cont|image;"')
    assert "http:" in url


def test_visualize_report(adr_service_query) -> None:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        my_report.visualize()
        my_report.visualize(new_tab=True)
        success = True
    except SyntaxError:
        success = False
    assert success is True


def test_iframe_report(adr_service_query) -> None:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        _ = my_report.get_iframe()
        success = True
    except SyntaxError:
        success = False
    assert success is True


@pytest.mark.ado_test
def test_unit_report_url(request) -> None:
    logfile = os.path.join(request.fspath.dirname, "outfile_3.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_url()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "" in line:
                err_msg = True
    assert err_msg


def test_unit_report_visualize(request) -> None:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    myreport.visualize()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error: could not obtain url for report" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_unit_report_iframe(request) -> None:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_iframe()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "No connection to any server" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_unit_no_url(request) -> None:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_url()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "No connection to any server" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_save_as_pdf(adr_service_query, request, get_exec) -> None:
    exec_basis = get_exec
    if exec_basis:
        success = False
        try:
            my_report = adr_service_query.get_report(report_name="My Top Report")
            pdf_file = os.path.join(request.fspath.dirname, "again_mytest")
            success = my_report.export_pdf(file_name=pdf_file)
        except Exception:
            success = False
    else:  # If no local installation, then skip this test
        success = True
    assert success is True


@pytest.mark.ado_test
def test_save_as_html(adr_service_query) -> None:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = my_report.export_html(directory_name="htmltest_again")
    except Exception:
        success = False
    assert success is True


def test_get_guid(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    guid = my_report.get_guid()
    assert len(guid) > 0


def test_get_report_script(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")

    # call web component <script> & defined expected output
    expected_script = """
        class ReportFetchComponent extends HTMLElement {
            constructor() {
                super();
            }

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

            connectedCallback(){
                const prefix = this.getAttribute('prefix') || "";
                const guid = this.getAttribute('guid') || "";
                const query = this.getAttribute('query').replaceAll("|", "%7C").replaceAll(";", "%3B") || "";
                const reportPath = this.getAttribute('reportURL') || "";
                const width = this.getAttribute('width') || "";
                const height = this.getAttribute('height') || "";
                if(prefix && guid){
                    // fetch report
                    return this.reportFetch(prefix, guid, query);
                }
                if(reportPath){
                    // use <iframe> instead
                    const iframeEle = document.createElement('iframe');
                    iframeEle.src = reportPath;
                    iframeEle.width = width;
                    iframeEle.height = height;
                    return this.appendChild(iframeEle);
                }
            }
        }
        customElements.define("adr-report", ReportFetchComponent);

    """
    clean_script = " ".join(my_report.get_report_script().split())
    clean_expected_script = " ".join(expected_script.split())
    # check script content
    script_check = clean_script == clean_expected_script

    assert script_check


def test_get_report_component(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")

    # call web component <adr-report> & define expected output
    # check 1: with prefix & host-style-path
    clean_web_component_prefix = " ".join(
        my_report.get_report_component("report", "", "style.css").split()
    )
    expected_prefix_attr = (
        f'prefix="report" guid="{my_report.get_guid()}" query="" host-style-path="style.css"'
    )
    clean_expected_web_component_prefix = " ".join(
        f"<adr-report {expected_prefix_attr}></adr-report>".split()
    )
    web_component_prefix_check = clean_web_component_prefix == clean_expected_web_component_prefix

    # check 2: NO prefix & host-style-path
    clean_web_component_iframe = " ".join(my_report.get_report_component().split())
    expected_iframe_attr = f'reportURL="{my_report.get_url()}" width="1000" height="800"'
    clean_expected_web_component_iframe = " ".join(
        f"<adr-report {expected_iframe_attr}></adr-report>".split()
    )
    web_component_iframe_check = clean_web_component_iframe == clean_expected_web_component_iframe

    assert web_component_prefix_check and web_component_iframe_check
