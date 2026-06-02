import os
import shutil
import hashlib
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# 尝试导入安全删除库，如果失败则使用 os.remove（给出警告）
try:
    from send2trash import send2trash
    SAFE_DELETE = True
except ImportError:
    SAFE_DELETE = False

# 可选：用于更精确的文件类型检测（如果未安装则不影响核心功能）
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

# 可选：用于图片预览（本工具未直接使用，但保留以作扩展）
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class FileCleanerApp:
    def __init__(self, root):
         self.root = root
         self.root.title("文件智理助手 - 智能整理+重复清理")
         self.root.geometry("700x500")
         self.root.resizable(True, True)

         # 变量
         self.folder_path = tk.StringVar()
         self.duplicates_to_delete = []  # 存储待删除的重复文件路径

        # 先创建界面（包括 log_text）
         self.create_widgets()

        # 后加载规则（此时 log_text 已存在，可正常输出日志）
         self.rules = self.load_rules()

    def create_widgets(self):
        # 选择文件夹区域
        frame_top = ttk.LabelFrame(self.root, text="目标文件夹", padding=10)
        frame_top.pack(fill=tk.X, padx=10, pady=5)

        ttk.Entry(frame_top, textvariable=self.folder_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_top, text="浏览", command=self.select_folder).pack(side=tk.LEFT, padx=5)

        # 按钮区域
        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(fill=tk.X, padx=10, pady=5)

        self.organize_btn = ttk.Button(frame_buttons, text="开始整理文件", command=self.start_organize)
        self.organize_btn.pack(side=tk.LEFT, padx=5)

        self.duplicate_btn = ttk.Button(frame_buttons, text="查找并清理重复文件", command=self.start_duplicate_clean)
        self.duplicate_btn.pack(side=tk.LEFT, padx=5)

        # 进度条
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        # 日志区域
        frame_log = ttk.LabelFrame(self.root, text="操作日志", padding=5)
        frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = tk.Text(frame_log, wrap=tk.WORD, height=15)
        scrollbar = ttk.Scrollbar(frame_log, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path.set(folder_selected)
            self.log(f"已选择文件夹: {folder_selected}")

    def log(self, message):
        """在日志区域显示消息并自动滚动到底部"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def load_rules(self):
        """加载分类规则，优先读取rules.json，否则使用默认规则"""
        if os.path.exists("rules.json"):
            try:
                with open("rules.json", "r", encoding="utf-8") as f:
                    user_rules = json.load(f)
                    # 确保"其他"分类存在，放置未匹配的文件
                    if "其他" not in user_rules:
                        user_rules["其他"] = []
                    self.log("已加载自定义 rules.json")
                    return user_rules
            except Exception as e:
                self.log(f"加载 rules.json 失败，使用默认规则: {e}")

        self.log("未找到 rules.json，使用默认分类规则")
        return {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico"],
            "Docs": [".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".ppt", ".pptx"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Videos": [".mp4", ".mkv", ".flv", ".avi", ".mov"],
            "Music": [".mp3", ".wav", ".flac", ".aac"],
            "Code": [".py", ".js", ".html", ".css", ".cpp", ".c", ".java", ".go", ".rs"],
            "Others": []
        }

    def get_target_folder(self, ext):
        """根据扩展名返回目标子文件夹名"""
        ext = ext.lower()
        for category, extensions in self.rules.items():
            if ext in extensions:
                return category
        return "Others"

    def organize_files(self, base_path):
        """执行文件整理（按扩展名移动到子文件夹）"""
        if not os.path.isdir(base_path):
            self.log("错误：目标路径不存在或不是一个文件夹")
            return

        moved_count = 0
        # 遍历所有文件和文件夹（不进入已存在的目标分类文件夹，避免二次移动）
        # 简单起见，只处理当前目录下的文件，递归处理子目录（但跳过已存在的分类文件夹）
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                # 如果是已经存在的分类文件夹（如 Images、Docs等），则跳过以避免递归移动自身
                if item in self.rules.keys():
                    continue
                # 递归处理子文件夹（可选，此处为了彻底整理，递归进入）
                self.organize_files(item_path)
                continue

            # 处理文件
            if os.path.isfile(item_path):
                file_name, ext = os.path.splitext(item)
                target_cat = self.get_target_folder(ext)
                target_dir = os.path.join(base_path, target_cat)
                os.makedirs(target_dir, exist_ok=True)

                # 目标路径（如果重名则自动添加编号）
                target_path = os.path.join(target_dir, item)
                counter = 1
                while os.path.exists(target_path):
                    name, ext2 = os.path.splitext(item)
                    new_name = f"{name}_{counter}{ext2}"
                    target_path = os.path.join(target_dir, new_name)
                    counter += 1

                try:
                    shutil.move(item_path, target_path)
                    self.log(f"[整理] {item} -> {target_cat}/")
                    moved_count += 1
                except Exception as e:
                    self.log(f"[错误] 移动文件 {item} 失败: {e}")

        self.log(f"整理完成，共移动 {moved_count} 个文件")

    def compute_md5(self, file_path, block_size=8192, fast_mode=True):
        """计算文件MD5，fast_mode为True时只读取首尾各1MB以加快速度（适用于大文件去重）"""
        hash_md5 = hashlib.md5()
        file_size = os.path.getsize(file_path)
        if fast_mode and file_size > 2 * 1024 * 1024:  # 大于2MB的文件使用快速模式
            with open(file_path, "rb") as f:
                # 读取前1MB
                data = f.read(1024 * 1024)
                hash_md5.update(data)
                # 读取后1MB
                f.seek(max(0, file_size - 1024 * 1024))
                data = f.read(1024 * 1024)
                hash_md5.update(data)
        else:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(block_size), b""):
                    hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def find_duplicates(self, base_path):
        """扫描文件夹，返回字典 {md5: [文件路径列表]}，只有多于1个的才返回"""
        if not os.path.isdir(base_path):
            return {}
        # 规范化基础路径，确保使用系统标准路径格式
        base_path = os.path.normpath(os.path.abspath(base_path))
        hash_map = {}
        total_files = 0
        # 先统计总文件数用于进度条
        for root, dirs, files in os.walk(base_path):
            total_files += len(files)
        processed = [0]  # 用列表包装以在闭包中修改

        # 在主线程更新进度条的安全方法
        def update_progress(value):
            self.root.after(0, lambda v=value: self.progress.configure(value=v))

        for root, dirs, files in os.walk(base_path):
            for file in files:
                # 规范化文件路径，确保使用系统标准路径格式
                file_path = os.path.normpath(os.path.join(root, file))
                try:
                    md5 = self.compute_md5(file_path)
                    if md5 not in hash_map:
                        hash_map[md5] = []
                    hash_map[md5].append(file_path)
                except Exception as e:
                    self.log(f"[错误] 计算哈希失败 {file}: {e}")
                processed[0] += 1
                if processed[0] % 10 == 0:
                    update_progress((processed[0] / total_files) * 100)
        update_progress(100)
        # 过滤出重复的文件组（组内文件数>1）
        duplicates = {md5: paths for md5, paths in hash_map.items() if len(paths) > 1}
        return duplicates

    def show_duplicate_dialog(self, duplicates):
        """弹出窗口让用户选择要删除的重复文件（保留第一个）"""
        if not duplicates:
            self.log("未发现重复文件。")
            self._enable_buttons()
            return

        # 对话框关闭时的回调（包括点击X按钮）
        def on_dialog_close():
            dialog.destroy()
            self._enable_buttons()

        # 创建顶级窗口
        dialog = tk.Toplevel(self.root)
        dialog.title("清理重复文件")
        dialog.geometry("700x400")
        # 捕获窗口关闭事件（点击 X 按钮）
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        label = ttk.Label(frame, text="请勾选要删除的重复文件（每组至少保留一个）", font=("Arial", 10))
        label.pack(anchor=tk.W)

        # 使用Canvas+ScrollableFrame显示多组复选框
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 存储复选框变量
        check_vars = []

        for md5, paths in duplicates.items():
            group_label = ttk.Label(scrollable_frame, text=f"重复组 (MD5: {md5[:8]}...)", font=("Arial", 9, "bold"))
            group_label.pack(anchor=tk.W, pady=(10, 0))
            # 保留第一个文件（不提供删除选项），其余提供复选框
            for idx, path in enumerate(paths):
                var = tk.BooleanVar()
                check_vars.append((var, path))
                if idx == 0:
                    # 第一个文件默认保留，不可删除
                    cb = ttk.Checkbutton(scrollable_frame, text=path, variable=var, state="disabled")
                    cb.pack(anchor=tk.W, padx=20)
                else:
                    cb = ttk.Checkbutton(scrollable_frame, text=path, variable=var)
                    cb.pack(anchor=tk.W, padx=20)

        def confirm_delete():
            to_delete = [path for var, path in check_vars if var.get()]
            if not to_delete:
                messagebox.showinfo("提示", "没有选择任何文件。")
                return
            # 确认删除
            if messagebox.askyesno("确认删除", f"将删除 {len(to_delete)} 个重复文件，是否继续？"):
                deleted_count = 0
                for path in to_delete:
                    # 规范化路径，确保使用系统标准格式
                    normalized_path = os.path.normpath(os.path.abspath(path))
                    try:
                        # 先检查文件是否存在
                        if not os.path.exists(normalized_path):
                            self.log(f"[警告] 文件不存在，跳过: {normalized_path}")
                            continue
                        if SAFE_DELETE:
                            try:
                                send2trash(normalized_path)
                            except Exception:
                                # send2trash 失败时回退到 os.remove
                                self.log(f"[提示] send2trash 失败，改用直接删除: {normalized_path}")
                                os.remove(normalized_path)
                        else:
                            os.remove(normalized_path)
                        self.log(f"[清理] 已删除重复文件: {normalized_path}")
                        deleted_count += 1
                    except FileNotFoundError:
                        self.log(f"[警告] 文件已被移除，跳过: {normalized_path}")
                    except PermissionError:
                        self.log(f"[错误] 没有权限删除: {normalized_path}")
                    except Exception as e:
                        self.log(f"[错误] 删除失败 {normalized_path}: {e}")
                self.log(f"重复文件清理完成，共删除 {deleted_count} 个文件。")
                on_dialog_close()
            else:
                self.log("已取消删除操作。")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="确认删除所选文件", command=confirm_delete).pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="取消", command=on_dialog_close).pack(side=tk.RIGHT)

    def start_organize(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showwarning("警告", "请先选择一个文件夹")
            return
        # 禁用按钮，启动线程
        self.organize_btn.config(state=tk.DISABLED)
        self.duplicate_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        thread = threading.Thread(target=self._organize_thread, args=(folder,))
        thread.start()

    def _organize_thread(self, folder):
        try:
            self.organize_files(folder)
        except Exception as e:
            self.log(f"整理过程发生异常: {e}")
        finally:
            self.root.after(0, self._enable_buttons)

    def start_duplicate_clean(self):
        folder = self.folder_path.get()
        if not folder:
            messagebox.showwarning("警告", "请先选择一个文件夹")
            return
        self.organize_btn.config(state=tk.DISABLED)
        self.duplicate_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        thread = threading.Thread(target=self._duplicate_thread, args=(folder,))
        thread.start()

    def _duplicate_thread(self, folder):
        try:
            self.log("正在扫描重复文件，请稍候...")
            duplicates = self.find_duplicates(folder)
            self.log(f"扫描完成，发现 {len(duplicates)} 组重复文件。")
            # 对话框关闭时会自动调用 _enable_buttons 恢复按钮
            self.root.after(0, lambda: self.show_duplicate_dialog(duplicates))
        except Exception as e:
            self.log(f"扫描重复文件出错: {e}")
            self.root.after(0, self._enable_buttons)

    def _enable_buttons(self):
        self.organize_btn.config(state=tk.NORMAL)
        self.duplicate_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = FileCleanerApp(root)
    # 显示启动提示
    if not SAFE_DELETE:
        app.log("提示: send2trash 未安装，删除操作将永久删除文件（不经过回收站）。建议执行: pip install send2trash")
    root.mainloop()