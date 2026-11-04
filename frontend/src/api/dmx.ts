import { api } from "@/api/client";
import type { DmxStatusPublic } from "@/api/types";

export const dmxApi = {
  status: () => api.get<DmxStatusPublic>("/dmx/status"),
  // Accepts the show project (.qxw) and fixture library (.qxf) files
  // together, sorted server-side by extension -- the Upload page's
  // combined "Projet QLC+" field.
  upload: (files: File[]) => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    return api.postForm<{ message: string }>("/dmx/upload", formData);
  },
};
