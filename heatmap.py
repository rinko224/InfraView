import numpy as np
import matplotlib.pyplot as plt

def create_thermal_image(
    csv_path: str, 
    output_path: str = None,
    cmap: str = 'inferno',
    interpolation: str = 'gaussian',
    title: str = 'High-Precision Thermal Image',
    cbar_label: str = 'Temperature (°C)',
    vmin_percentile: int = 2,
    vmax_percentile: int = 98,
    add_annotations: bool = True) -> bool:

    try:
        temperature_data = np.loadtxt(csv_path, delimiter=',')
    except FileNotFoundError:
        print(f"Error: File not found at '{csv_path}'.")
        return False
    except Exception as e:
        print(f"Error reading file '{csv_path}': {e}")
        return False
    
    if temperature_data.ndim != 2:
        print(f"Error: Data in '{csv_path}' is not a valid 2D matrix.")
        return False

    # --- 2. 动态计算颜色范围 (不变) ---
    vmin = np.percentile(temperature_data, vmin_percentile)
    vmax = np.percentile(temperature_data, vmax_percentile)
    if np.isclose(vmin, vmax):
        vmax = vmin + 1

    print(f"Auto-calculated color range: Min={vmin:.2f}, Max={vmax:.2f}")

    # --- 3. 创建图像 ---
    fig, ax = plt.subplots(figsize=(12, 9), dpi=120)
    
    heatmap = ax.imshow(temperature_data, 
                        cmap=cmap, 
                        vmin=vmin, 
                        vmax=vmax,
                        interpolation=interpolation)

    # --- 4. 配置图表元素 (不变) ---
    fig.colorbar(heatmap, ax=ax, label=cbar_label, extend='both')
    ax.set_title(title, fontsize=16, weight='bold')
    ax.axis('off')

    if add_annotations:
        # 找到真实的最高/最低温及其在矩阵中的位置
        max_val = np.max(temperature_data)
        min_val = np.min(temperature_data)
        
        # np.unravel_index 将一维索引转换为 (行, 列) 坐标
        max_loc = np.unravel_index(np.argmax(temperature_data), temperature_data.shape)
        min_loc = np.unravel_index(np.argmin(temperature_data), temperature_data.shape)
        
        # 定义标注文本的样式（半透明黑色背景，白色文字）
        text_props = dict(boxstyle='round,pad=0.4', fc='black', alpha=0.6, ec='none')
        
        # 添加最高温标注
        ax.text(max_loc[1], max_loc[0], f' H: {max_val:.2f} ',
                color='white', ha='center', va='center', fontsize=10, bbox=text_props)
        
        # 添加最低温标注
        ax.text(min_loc[1], min_loc[0], f' L: {min_val:.2f} ',
                color='white', ha='center', va='center', fontsize=10, bbox=text_props)
        
        # 添加标记点，使位置更显眼
        ax.plot(max_loc[1], max_loc[0], '+', color='white', markersize=12, mew=2.5) # mew是标记线宽
        ax.plot(min_loc[1], min_loc[0], '_', color='white', markersize=12, mew=2.5)

    # --- 5. 显示或保存图像 (不变) ---
    try:
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
            print(f"Image successfully saved to: {output_path}")
        else:
            plt.show()
        
        plt.close(fig)
        return True
    except Exception as e:
        print(f"An error occurred while displaying or saving the image: {e}")
        plt.close(fig)
        return False