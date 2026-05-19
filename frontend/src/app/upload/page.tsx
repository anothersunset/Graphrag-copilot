"use client";

import { useState, useCallback } from "react";

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<Array<{ fileName: string; status: string; chunks: number; entities: number; }>>([]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...droppedFiles]);
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    const newResults = [];

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("http://localhost:8000/api/documents/upload", {
          method: "POST",
          body: formData,
        });

        if (response.ok) {
          const data = await response.json();
          newResults.push({
            fileName: file.name,
            status: "成功",
            chunks: data.chunks_created,
            entities: data.entities_extracted,
          });
        } else {
          newResults.push({ fileName: file.name, status: "失败", chunks: 0, entities: 0 });
        }
      } catch {
        newResults.push({ fileName: file.name, status: "错误", chunks: 0, entities: 0 });
      }
    }

    setResults(newResults);
    setUploading(false);
    setFiles([]);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">知识上传</h1>
        <p className="text-gray-600">上传文档、图片、视频，自动构建知识库</p>
      </div>

      <div onDrop={onDrop} onDragOver={onDragOver} className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center hover:border-purple-500 transition cursor-pointer">
        <div className="text-6xl mb-4">📁</div>
        <p className="text-lg font-semibold mb-2">拖拽文件到此处</p>
        <p className="text-gray-500 mb-4">或点击选择文件</p>
        <input type="file" multiple accept=".pdf,.docx,.pptx,.txt,.md,.jpg,.jpeg,.png,.mp4,.wav,.mp3" onChange={handleFileSelect} className="hidden" id="file-input" />
        <label htmlFor="file-input" className="inline-block px-6 py-3 bg-purple-600 text-white rounded-lg cursor-pointer hover:bg-purple-700 transition">选择文件</label>
        <p className="text-xs text-gray-400 mt-4">支持 PDF、Word、PPT、图片、视频、音频等格式</p>
      </div>

      {files.length > 0 && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold mb-4">待上传文件 ({files.length})</h3>
          <div className="space-y-2">
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">📄</span>
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                <button onClick={() => removeFile(index)} className="text-red-500 hover:text-red-700">✕</button>
              </div>
            ))}
          </div>
          <button onClick={handleUpload} disabled={uploading} className="mt-4 w-full py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition">
            {uploading ? "上传中..." : "开始上传"}
          </button>
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold mb-4">上传结果</h3>
          <div className="space-y-2">
            {results.map((r, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="font-medium">{r.fileName}</span>
                <span className="text-sm">{r.status} · chunks: {r.chunks} · entities: {r.entities}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
