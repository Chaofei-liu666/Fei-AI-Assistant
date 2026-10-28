import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("toolbar", {
  action: (name: "back" | "forward" | "reload" | "close") => ipcRenderer.invoke(`career-browser:${name}`),
  onState: (listener: (state: unknown) => void) => ipcRenderer.on("browser-state", (_event, state) => listener(state)),
});
