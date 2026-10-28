import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("feiDesktop", {
  platform: "windows",
  careerBrowser: {
    open: (input: {url: string; applicationId?: string}) => ipcRenderer.invoke("career-browser:open", input),
    close: () => ipcRenderer.invoke("career-browser:close"),
    back: () => ipcRenderer.invoke("career-browser:back"),
    forward: () => ipcRenderer.invoke("career-browser:forward"),
    reload: () => ipcRenderer.invoke("career-browser:reload"),
    reviewApplication: (input: {applicationId: string}) => ipcRenderer.invoke("career-browser:review", input),
    getState: () => ipcRenderer.invoke("career-browser:state"),
  },
});
