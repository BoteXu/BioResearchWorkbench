"""CI-only browser interaction checks with synthetic data, not device certification."""
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import web_gateway


def main():
    from playwright.sync_api import sync_playwright, expect
    token = 'synthetic-browser-token-'+'x'*40
    calls = []
    def dispatch(data):
        calls.append(data)
        if data['operation']=='catalog':
            return {'tools':[{'name':'fixture_audit','category':'biomedical','description':'Synthetic browser check',
                              'required_parameters':[{'name':'rows','type':'list'}],'optional_parameters':[]}]}
        if data['operation']=='status':
            return {'state':'synthetic_ready'}
        if data.get('category')=='molecular_biology':
            assert data['name']=='guide_molecular_drylab'
            return {'state':'plan_only','qc':['synthetic QC requirement'],'issues':[], 'deferred':['synthetic missing result']}
        assert data=={'operation':'tool','category':'biomedical','name':'fixture_audit','parameters':{'rows':[{'fixture':'public'}]}}
        return {'decision':'synthetic_pass'}
    server = ThreadingHTTPServer(('localhost',0),web_gateway.handler(token,dispatch))
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for width in (360,1200):
                page = browser.new_page(viewport={'width':width,'height':800})
                page.goto(f'http://localhost:{server.server_port}')
                expect(page.locator('h1')).to_have_text('BioResearchWorkbench 工具连接')
                page.locator('#token').fill(token)
                page.locator('#connect').click()
                page.locator('summary').click()
                expect(page.locator('#tool option')).to_have_count(1)
                page.locator('[data-name="rows"]').fill(json.dumps([{'fixture':'public'}]))
                page.locator('#run').click()
                expect(page.locator('#result')).to_contain_text('synthetic_pass')
                assert page.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
                assert page.evaluate('() => localStorage.length === 0 && sessionStorage.length === 0 && document.cookie === ""')
                with page.expect_download() as downloaded:
                    page.locator('#download').click()
                assert downloaded.value.suggested_filename=='biomni-result.json'
                for field in ['species','model','unit','contrast','version']:
                    page.locator('#question-'+field).fill('synthetic')
                page.locator('#question-task').select_option('splicing')
                page.locator('#question-plan').click()
                expect(page.locator('#decision')).to_contain_text('分析尚未运行')
                expect(page.locator('#qc-issues')).to_contain_text('synthetic QC requirement')
                expect(page.locator('#missing-list')).to_contain_text('synthetic missing result')
                page.close()
            browser.close()
        assert sum(c['operation']=='tool' for c in calls)==4
        print('DESKTOP_AND_MOBILE_BROWSER_CHECKS_OK')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__=='__main__':
    main()
