import { app, BaseWindow, ipcMain, session, WebContentsView } from "electron";
import { createHash } from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";

const FEI_URL = process.env.FEI_DESKTOP_URL || "http://127.0.0.1:3000";
const FEI_API = process.env.FEI_DESKTOP_API || "http://127.0.0.1:8000";
const TOOLBAR_HEIGHT = 42;
const SPLIT_RATIO = .56;

let window: BaseWindow;
let appView: WebContentsView;
let browserView: WebContentsView | undefined;
let toolbarView: WebContentsView | undefined;
let activeApplicationId: string | undefined;

function safeWebUrl(raw: unknown): string {
  if (typeof raw !== "string" || raw.length > 2048) throw new Error("invalid_url");
  const url = new URL(raw);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("invalid_url");
  return url.toString();
}

function bounds() {
  const { width, height } = window.getContentBounds();
  if (!browserView || !toolbarView) {
    appView.setBounds({x:0,y:0,width,height});
    return;
  }
  const left = Math.max(560, Math.floor(width * SPLIT_RATIO));
  appView.setBounds({x:0,y:0,width:left,height});
  toolbarView.setBounds({x:left,y:0,width:width-left,height:TOOLBAR_HEIGHT});
  browserView.setBounds({x:left,y:TOOLBAR_HEIGHT,width:width-left,height:height-TOOLBAR_HEIGHT});
}

function state() {
  const wc = browserView?.webContents;
  return {
    open: Boolean(wc && !wc.isDestroyed()),
    url: wc?.getURL(),
    title: wc?.getTitle(),
    canGoBack: wc?.navigationHistory.canGoBack() ?? false,
    canGoForward: wc?.navigationHistory.canGoForward() ?? false,
    applicationId: activeApplicationId,
  };
}

function publishState() {
  const value = state();
  if (toolbarView && !toolbarView.webContents.isDestroyed()) toolbarView.webContents.send("browser-state", value);
  if (appView && !appView.webContents.isDestroyed()) appView.webContents.send("browser-state", value);
}

function createBrowser() {
  if (browserView && toolbarView) return;
  const careerSession = session.fromPartition("persist:fei-career-browser");
  careerSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  browserView = new WebContentsView({webPreferences:{
    session: careerSession, contextIsolation: true, sandbox: true, nodeIntegration: false,
    webSecurity: true, allowRunningInsecureContent: false,
  }});
  toolbarView = new WebContentsView({webPreferences:{
    preload: path.join(__dirname,"toolbar-preload.js"), contextIsolation:true, sandbox:true, nodeIntegration:false,
  }});
  browserView.webContents.setWindowOpenHandler(({url}) => {
    try { void browserView?.webContents.loadURL(safeWebUrl(url)); } catch { /* deny unsafe target */ }
    return {action:"deny"};
  });
  browserView.webContents.on("will-navigate", (event, url) => {
    try { safeWebUrl(url); } catch { event.preventDefault(); }
  });
  browserView.webContents.on("did-navigate", publishState);
  browserView.webContents.on("did-navigate-in-page", publishState);
  browserView.webContents.on("page-title-updated", publishState);
  window.contentView.addChildView(toolbarView);
  window.contentView.addChildView(browserView);
  void toolbarView.webContents.loadFile(path.join(__dirname,"../renderer/toolbar.html"));
  bounds();
}

function closeBrowser() {
  activeApplicationId = undefined;
  if (browserView) { window.contentView.removeChildView(browserView); browserView.webContents.close(); browserView = undefined; }
  if (toolbarView) { window.contentView.removeChildView(toolbarView); toolbarView.webContents.close(); toolbarView = undefined; }
  bounds(); publishState();
}

function inferStatus(text: string) {
  const stages: [string, RegExp][] = [
    ["offer", /(?:offer|录用|拟录用)/i], ["interview", /(?:面试|一面|二面|终面|hr面)/i],
    ["assessment", /(?:测评|笔试|在线测试)/i], ["screening", /(?:筛选中|审核中|简历筛选)/i],
    ["rejected", /(?:未通过|不合适|流程终止|淘汰)/i], ["applied", /(?:已投递|申请成功|已申请)/i],
  ];
  return stages.find(([, pattern]) => pattern.test(text))?.[0];
}

async function reviewApplication(applicationId: string) {
  if (!browserView || activeApplicationId !== applicationId) throw new Error("open_application_record_page_first");
  const wc = browserView.webContents;
  const observed = await wc.executeJavaScript(`(() => ({title: document.title.slice(0,500), text: (document.body?.innerText || '').slice(0,12000)}))()`, true) as {title:string;text:string};
  const text = `${observed.title}\n${observed.text}`;
  const loginRequired = /请登录|登录后|sign in|log in|账号登录/i.test(text);
  const captchaRequired = /验证码|滑块|人机验证|captcha/i.test(text);
  const status = loginRequired || captchaRequired ? undefined : inferStatus(text);
  const screenshot = await wc.capturePage();
  const screenshotSha256 = createHash("sha256").update(screenshot.toPNG()).digest("hex");
  const operationId = createHash("sha256").update(`${applicationId}\n${wc.getURL()}\n${Date.now()}`).digest("hex").slice(0,32);
  const response = await fetch(`${FEI_API}/api/career/applications/${encodeURIComponent(applicationId)}/review-observations`, {
    method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({
      operation_id:operationId, application_id:applicationId, page_url:wc.getURL(),
      observed_status:status, confidence:status ? .9 : 0, page_title:observed.title,
      visible_text:observed.text, screenshot_sha256:screenshotSha256, login_required:loginRequired,
      captcha_required:captchaRequired,
    }),
  });
  if (!response.ok) throw new Error(`review_failed_${response.status}`);
  const result = await response.json() as {id:string;observed_status?:string;confidence:number;blocked:boolean};
  return {ok:true,reviewId:result.id,observedStatus:result.observed_status,confidence:result.confidence,
          requiresUserAction:true,blocked:result.blocked};
}

function registerIpc() {
  ipcMain.handle("career-browser:open", async (_event, input: {url:string;applicationId?:string}) => {
    const url = safeWebUrl(input?.url); createBrowser(); activeApplicationId = input.applicationId;
    await browserView!.webContents.loadURL(url); publishState(); return {ok:true};
  });
  ipcMain.handle("career-browser:close", () => { closeBrowser(); return {ok:true}; });
  ipcMain.handle("career-browser:back", () => { if (browserView?.webContents.navigationHistory.canGoBack()) browserView.webContents.navigationHistory.goBack(); return {ok:true}; });
  ipcMain.handle("career-browser:forward", () => { if (browserView?.webContents.navigationHistory.canGoForward()) browserView.webContents.navigationHistory.goForward(); return {ok:true}; });
  ipcMain.handle("career-browser:reload", () => { browserView?.webContents.reload(); return {ok:true}; });
  ipcMain.handle("career-browser:state", () => state());
  ipcMain.handle("career-browser:review", (_event, input: {applicationId:string}) => reviewApplication(input.applicationId));
}

app.whenReady().then(async () => {
  window = new BaseWindow({width:1440,height:900,minWidth:1040,minHeight:680,backgroundColor:"#f6f7f8",title:"Fei 智能助手"});
  appView = new WebContentsView({webPreferences:{preload:path.join(__dirname,"preload.js"),contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true}});
  appView.webContents.setWindowOpenHandler(({url}) => { try { createBrowser(); void browserView!.webContents.loadURL(safeWebUrl(url)); } catch {} return {action:"deny"}; });
  window.contentView.addChildView(appView); bounds(); window.on("resize",bounds);
  window.on("closed", () => { browserView?.webContents.close(); toolbarView?.webContents.close(); appView.webContents.close(); });
  registerIpc();
  await appView.webContents.loadURL(FEI_URL);
});

app.on("window-all-closed", () => app.quit());
