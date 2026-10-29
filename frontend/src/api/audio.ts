import { api } from "@/api/client";
import type { AudioStatusPublic } from "@/api/types";

export const audioApi = {
  status: () => api.get<AudioStatusPublic>("/audio/status"),
  play: () => api.post<AudioStatusPublic>("/audio/play", undefined),
  playTest: () => api.post<AudioStatusPublic>("/audio/test", undefined),
  stop: () => api.post<AudioStatusPublic>("/audio/stop", undefined),
  setVolume: (volume: number) =>
    api.post<AudioStatusPublic>("/audio/volume", { volume }),
  setLoop: (enabled: boolean) =>
    api.post<AudioStatusPublic>("/audio/loop", { enabled }),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm<AudioStatusPublic>("/audio/upload", formData);
  },
  uploadTest: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.postForm<AudioStatusPublic>("/audio/upload-test", formData);
  },
};
