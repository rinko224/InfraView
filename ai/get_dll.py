import urllib.request
import zipfile
import os
import shutil

# 这是一个临时的自动下载脚本，用于获取 libusb-1.0.dll
def download_libusb():
    # libusb 官方 release 的下载链接 (7z格式解压麻烦，这里使用 nuget 的包作为源，因为它是zip)
    url = "https://www.nuget.org/api/v2/package/libusb-native/1.0.26.1"
    zip_path = "libusb_pkg.zip"
    
    print("正在下载 libusb 库...")
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as e:
        print(f"下载失败: {e}")
        return

    print("正在解压...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Nuget 包里的结构通常是 runtimes/win-x64/native/libusb-1.0.dll
            # 我们只提取我们需要的文件
            target_file = "runtimes/win-x64/native/libusb-1.0.dll"
            extract_path = zip_ref.extract(target_file)
            
            # 移动到当前目录
            shutil.move(extract_path, "./libusb-1.0.dll")
            print("✅ 成功！libusb-1.0.dll 已下载并放置在当前目录。")
            
    except Exception as e:
        print(f"解压失败: {e}")
    finally:
        # 清理临时文件
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists("runtimes"):
            shutil.rmtree("runtimes")

if __name__ == "__main__":
    download_libusb()