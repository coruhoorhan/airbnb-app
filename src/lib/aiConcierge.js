import { execFile } from "child_process";

export function generateAiResponse(message) {
  return new Promise((resolve) => {
    execFile(
      "python3",
      ["/opt/airbnb-app/magda_airbnb_bridge.py", "chat", message],
      (error, stdout, stderr) => {
        if (error) {
          resolve({
            response: "Bağlantı esnasında bir hata oluştu. Lütfen tekrar deneyin.",
            recommendations: []
          });
          return;
        }
        try {
          const data = JSON.parse(stdout);
          resolve({
            response: data.response || "Talebinizi inceledim, işte bulduğum seçenekler:",
            recommendations: data.recommendations || []
          });
        } catch (parseErr) {
          resolve({
            response: stdout || "Yanıt işlenemedi.",
            recommendations: []
          });
        }
      }
    );
  });
}
