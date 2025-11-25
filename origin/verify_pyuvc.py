# 文件名: verify_pyuvc.py

print("--- PyUVC 库安装与导入验证程序 ---")

try:
    # 第1步：尝试用官方方式导入 pyuvc
    import pyuvc
    print("[成功] 步骤 1: 成功执行 'import pyuvc'。")

    # 第2步：尝试访问库的版本号，这是检查库是否完整的标准方法
    version = pyuvc.__version__
    print(f"[成功] 步骤 2: 成功获取 pyuvc 版本号: {version}")

    # 第3步：尝试访问之前导致错误的 Context 类
    # 我们只访问它，不创建实例
    context_class = pyuvc.Context
    print(f"[成功] 步骤 3: 成功访问 'pyuvc.Context'。它是一个: {context_class}")
    
    # 第4步：尝试访问 error 子模块
    error_module = pyuvc.error
    print(f"[成功] 步骤 4: 成功访问 'pyuvc.error'。它是一个: {error_module}")

    print("\n[结论] 验证通过！您的 'pyuvc' 库已正确安装，并且必须通过 'import pyuvc' 来使用。")
    print("      请在您的主程序中坚持使用这种导入方式。")

except ImportError:
    print("\n[失败] 无法导入 'pyuvc'。")
    print("      请确认您已经成功运行了 'pip install pyuvc'。")

except AttributeError as e:
    print(f"\n[失败] 发生了 AttributeError: {e}")
    print("      这通常意味着库的安装不完整，或者您可能有一个旧版本。")
    print("      请尝试强制重新安装: pip install --upgrade --force-reinstall pyuvc")

except Exception as e:
    print(f"\n发生了未知错误: {e}")