const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ariaSetup", {
  saveToken: (token, remember, captchaKey, captchaProvider) =>
    ipcRenderer.invoke("setup:save-token", { token, remember, captchaKey, captchaProvider }),
  cancel: () => ipcRenderer.send("setup:cancel"),
});

contextBridge.exposeInMainWorld("ariaDesktop", {
  perform: (action) => ipcRenderer.invoke("desktop:action", action),
});
