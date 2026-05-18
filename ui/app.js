function app() {
  return {
    screen: "loading",
    busy: false,
    error: "",
    bootError: "",
    username: "",
    form: { user: "", pass: "", remember: false },
    courses: [],
    selected: [],
    progress: [],
    downloading: false,

    log(msg, ...args) {
      console.log("[ui]", msg, ...args);
    },

    async waitForApi() {
      for (let i = 0; i < 100; i++) {
        if (window.pywebview?.api?.autoLogin) return true;
        await new Promise((r) => setTimeout(r, 100));
      }
      return false;
    },

    async boot() {
      this.log("boot start");
      try {
        const ok = await this.waitForApi();
        if (!ok) {
          this.bootError = "Bridge pywebview non disponibile dopo 10s.";
          this.screen = "error";
          return;
        }
        this.log("api ready, calling autoLogin");
        const res = await window.pywebview.api.autoLogin();
        this.log("autoLogin →", res);
        if (res.firstRun) {
          this.screen = "login";
          return;
        }
        if (res.ok) {
          this.username = res.username;
          this.courses = res.courses;
          this.screen = "courses";
        } else {
          this.error = res.error || "Login fallito";
          this.screen = "login";
        }
      } catch (e) {
        this.log("boot error:", e);
        this.bootError = String(e?.message || e);
        this.screen = "error";
      }
    },

    async doLogin() {
      this.error = "";
      this.busy = true;
      try {
        this.log("login attempt for", this.form.user, "remember=", this.form.remember);
        const res = await window.pywebview.api.login(
          this.form.user, this.form.pass, this.form.remember
        );
        this.log("login result:", res);
        if (!res.ok) { this.error = res.error || "Errore"; return; }
        this.username = res.username;
        this.courses = res.courses;
        this.form.pass = "";
        this.screen = "courses";
      } catch (e) {
        this.error = String(e?.message || e);
      } finally {
        this.busy = false;
      }
    },

    async forgetAccount() {
      if (!confirm("Dimenticare l'account salvato? Dovrai reinserire le credenziali al prossimo avvio.")) return;
      await window.pywebview.api.forgetAccount();
      this.courses = [];
      this.selected = [];
      this.username = "";
      this.form = { user: "", pass: "", remember: false };
      this.screen = "login";
    },

    async logout() {
      await window.pywebview.api.logout();
      this.courses = [];
      this.selected = [];
      this.progress = [];
      this.screen = "login";
    },

    allSelected() {
      return this.courses.length > 0 && this.selected.length === this.courses.length;
    },
    toggleAll() {
      this.selected = this.allSelected() ? [] : this.courses.map((c) => c.code);
    },

    backToCourses() {
      this.log("backToCourses");
      this.screen = "courses";
    },

    startDownload() {
      this.progress = this.selected.map((code) => {
        const c = this.courses.find((x) => x.code === code);
        return {
          code, name: c.name, status: "queued", statusLabel: "in coda…",
          message: "", percent: 0, done: 0, total: 0,
        };
      });
      this.downloading = true;
      this.screen = "download";
      window.pywebview.api.download(this.selected);
    },

    onProgress(evt) {
      const row = this.progress.find((p) => p.code === evt.course_code);
      if (!row) return;
      if (evt.kind === "course_start") {
        row.status = "downloading";
        row.total = evt.total;
        row.done = 0;
        row.statusLabel = `0 / ${evt.total}`;
        row.percent = 0;
      } else if (evt.kind === "file") {
        row.done = evt.index;
        row.total = evt.total;
        row.message = `${evt.file} — ${evt.message}`;
        row.percent = Math.round((evt.index / Math.max(1, evt.total)) * 100);
        row.statusLabel = `${evt.index} / ${evt.total}`;
      } else if (evt.kind === "course_done") {
        row.status = "done";
        row.statusLabel = `${evt.downloaded} nuovi, ${evt.skipped} skip`;
        row.percent = 100;
      } else if (evt.kind === "course_error") {
        row.status = "error";
        row.statusLabel = "errore";
        row.message = evt.message;
      } else if (evt.kind === "all_done") {
        this.downloading = false;
      }
    },

    async openDownloads() {
      await window.pywebview.api.openDownloadsFolder();
    },
  };
}

window.notifyProgress = function (evtJson) {
  try {
    const root = document.querySelector("[x-data]");
    const data = Alpine.$data(root);
    data.onProgress(JSON.parse(evtJson));
  } catch (e) {
    console.error("notifyProgress failed:", e);
  }
};
