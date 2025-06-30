"""
Pan123 Scraper - 123云盘智能文件刮削器
=====================================

一个基于Flask的Web应用程序，用于管理和重命名123云盘中的媒体文件。

🎯 核心功能：
- 🎬 智能文件刮削：自动识别电影、电视剧信息
- 🤖 AI智能分组：基于内容自动分组和命名
- 📁 智能重命名：为文件夹生成标准化名称
- 🔄 批量操作：支持批量重命名、移动、删除
- 📊 性能监控：实时监控API性能和缓存命中率
- 🧹 智能缓存：LRU缓存系统，自动内存管理

🛡️ 技术特性：
- 安全性：敏感信息保护、命令注入防护、输入验证
- 高性能：多线程处理、智能缓存、QPS限制
- 可维护性：模块化设计、统一异常处理、代码重构
- 可观测性：性能监控、日志记录、统计分析

📋 架构组件：
- Flask Web框架：提供RESTful API接口
- LRU缓存系统：智能内存管理和过期清理
- 性能监控：API调用统计和缓存命中率分析
- 配置管理：统一配置验证和类型转换
- 异常处理：分层异常处理和错误恢复

作者: jonntd@gmail.com
版本: 3.0 (重构版)
最后更新: 2025-07-01
许可: MIT License
"""

# 标准库导入
import os
import json
import logging
import threading
import datetime
import requests
import traceback
import re
import sys
import subprocess
import time
import base64
from collections import deque
import hashlib
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler

# 第三方库导入
from flask import Flask, render_template, request, jsonify
from collections import OrderedDict

# ================================
# 应用程序初始化和常量定义
# ================================

app = Flask(__name__)


# ================================
# LRU缓存实现
# ================================

class LRUCache:
    """
    线程安全的LRU缓存实现

    Features:
    - 自动过期机制
    - 线程安全
    - 内存限制
    """

    def __init__(self, max_size=1000, ttl=3600):
        """
        初始化LRU缓存

        Args:
            max_size (int): 最大缓存条目数
            ttl (int): 生存时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key, record_stats=True):
        """获取缓存值"""
        with self.lock:
            if key not in self.cache:
                if record_stats and hasattr(self, '_cache_name'):
                    performance_monitor.record_cache_hit(self._cache_name, hit=False)
                return None

            value, timestamp = self.cache[key]

            # 检查是否过期
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                if record_stats and hasattr(self, '_cache_name'):
                    performance_monitor.record_cache_hit(self._cache_name, hit=False)
                return None

            # 移动到末尾（最近使用）
            self.cache.move_to_end(key)
            if record_stats and hasattr(self, '_cache_name'):
                performance_monitor.record_cache_hit(self._cache_name, hit=True)
            return value

    def put(self, key, value):
        """设置缓存值"""
        with self.lock:
            current_time = time.time()

            if key in self.cache:
                # 更新现有条目
                self.cache[key] = (value, current_time)
                self.cache.move_to_end(key)
            else:
                # 添加新条目
                if len(self.cache) >= self.max_size:
                    # 移除最旧的条目
                    self.cache.popitem(last=False)

                self.cache[key] = (value, current_time)

    def delete(self, key):
        """删除缓存条目"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()

    def cleanup_expired(self):
        """清理过期条目"""
        with self.lock:
            current_time = time.time()
            expired_keys = []

            for key, (_, timestamp) in self.cache.items():
                if current_time - timestamp > self.ttl:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]

            return len(expired_keys)

    def size(self):
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)

    def stats(self):
        """获取缓存统计信息"""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl': self.ttl
            }

    def __contains__(self, key):
        """支持 'in' 操作符"""
        with self.lock:
            if key not in self.cache:
                return False

            _, timestamp = self.cache[key]

            # 检查是否过期
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return False

            return True

    def __getitem__(self, key):
        """支持 cache[key] 操作"""
        return self.get(key)

    def __setitem__(self, key, value):
        """支持 cache[key] = value 操作"""
        self.put(key, value)


# 配置文件路径
CONFIG_FILE = 'config.json'

# TMDB API基础URL
TMDB_API_URL_BASE = "https://api.themoviedb.org/3"

# ================================
# AI提示词模板定义
# ================================

# 媒体信息提取提示词模板
# 用于从文件名中提取电影、电视剧等媒体信息并匹配TMDB数据
EXTRACTION_PROMPT = """
你是一个专业的媒体信息提取和元数据匹配助手。
**目标：** 根据提供的电影、电视剧或番剧文件名列表，智能解析每个文件名，并从在线数据库中匹配并提取详细元数据，然后将所有结果汇总为一个JSON数组。
**输入：** 一个包含多个电影/电视剧/番剧文件名，每行一个文件名。
**输出：** 严格的JSON格式结果。

⚠️ **重要提醒：信息提取优先级**
1. **🌏 中文优先原则**：**默认使用中文标题，次要使用英文标题**。所有输出的 `title` 字段必须优先使用中文，如果数据库没有中文标题才使用英文。
2. **文件夹名称信息优先**：如果文件路径包含文件夹名称（如"冒险者 (1917)[tmdbid=31819]"），优先使用文件夹中的标题和年份信息
3. **TMDB ID直接匹配**：如果文件名包含[tmdbid=数字]，直接使用该ID，不要搜索其他电影
4. **年份信息严格遵守**：文件名中的年份信息必须严格遵守，不要匹配年份差异过大的电影
5. **标题准确性**：优先保持原始中文标题，不要随意"翻译"为英文
6. **🎯 动画角色识别**：如果文件名包含特定动画角色名称，必须正确识别所属系列：
   - 基尔兽、大耳兽、古拉兽、亚古兽、加布兽等 → 数码宝贝系列
   - 皮卡丘、小火龙、杰尼龟等 → 宝可梦系列
   - 路飞、索隆、娜美等 → 海贼王系列
   - 鸣人、佐助、小樱等 → 火影忍者系列
**处理步骤（对每个文件名重复执行）：**
1.  **文件名解析与信息提取：**
    *   **核心原则：** 尽最大可能识别并移除所有非标题的技术性后缀、前缀及中间标记，提取出最可能、最简洁的原始标题部分。
    *   **需要移除的常见标记（但不限于）：**
        *   **分辨率:** 2160p, 1080p, 720p, 4K, UHD, SD
        *   **视频编码:** H264, H265, HEVC, x264, x265, AVC, VP9, AV1, DivX, XviD
        *   **来源/压制:** WEB-DL, BluRay, HDTV, WEBRip, BDRip, DVDRip, KORSUB, iNTERNAL, Remux, PROPER, REPACK, RETAIL, Disc, VOSTFR, DUBBED, SUBBED, FanSub, CBR, VBR, P2P
        *   **音频编码/声道:** DDP5.1, Atmos, DTS-HD MA, TrueHD, AC3, AAC, FLAC, DD+7.1, Opus, MP3, 2.0, 5.1, 7.1, Multi-Audio, Dual Audio
        *   **HDR/杜比视界:** DV, HDR, HDR10, DoVi, HLG, HDR10+, WCG
        *   **版本信息:** Director's Cut, Extended, Uncut, Theatrical, Special Edition, Ultimate Edition, Remastered, ReCut, Criterion, IMAX, Limited Series
        *   **发布组/站点:** [RARBG], [YTS.AM], FGT, CtrlHD, DEFLATE, xixi, EVO, GHOULS, FRDS, PANTHEON, WiKi, CHDBits, OurBits, MTeam, LoL, TRP, FWB, x264-GROUP, VCB-Studio, ANi, Lilith-Raws
        *   **季/集号:** S01E01, S1E1, Season 1 Episode 1, Part 1, P1, Ep01, Vol.1, 第1季第1集, SP (Special), OVA, ONA, Movie (对于番剧剧场版), NCED, NCOP (无字幕OP/ED), 文件名开头的数字（如"01. 标题"、"02. 标题"等）
        *   **年份:** (2023), [2023], .2023., _2023_
        *   **其他:** (R), _ , -, ., ~ , { }, [ ], ` `, + 等常见分隔符，以及广告词、多余的空格、多余的语言代码（如CHS, ENG, JPN）等。
    *   **提取以下结构化信息：**
        *   **中文标题 (title):** 最可能、最简洁的电影/电视剧/番剧中文标题。**优先级：中文标题 > 英文标题**。如果文件名包含中文，必须提取中文标题；如果只有英文，则提取英文标题。
        *   **年份 (year):** 识别到的发行年份。
        *   **季号 (season):** 电视剧或番剧的季号，通常为数字。
        *   **集号 (episode):** 电视剧或番剧的集号，通常为数字，例如：'/我的接收/九丹 Jiudan.EP01-37.2013.1080p/11.mp4', episode is 11。
        *   **部分 (part):** 如果是电影的特定部分（如 Part 1, Disc 2，非系列电影的续集），或番剧的OVA/SP等特殊集。

2.  **在线数据库搜索与匹配：**
    *   **操作指示：** **必须使用你的联网搜索工具**。
    *   **搜索关键词构建：**
        *   **优先使用中文标题**：如果解析出中文 `title`，优先使用中文标题进行搜索。
        *   **英文标题作为补充**：如果中文搜索无结果，再使用英文标题搜索。
        *   **搜索策略**：`"中文标题 年份 TMDB"` → `"English Title 年份 TMDB"`
        *   示例搜索词：`"冒险者 1917 TMDB"`, `"一路向东 1920 TMDB"`, `"The Adventurer 1917 TMDB"`。
    *   **优先顺序（中文优先）：**
        1.  **豆瓣电影 (Douban):** 对于中文内容的首选，提供准确的中文标题和信息。
        2.  **themoviedb.org (TMDB):** 针对电影和电视剧，支持多语言包括中文。
        3.  **AniDB:** 针对动画、动漫（番剧），支持中文标题。
        4.  **IMDb:** 作为补充数据源，主要提供英文信息。
        5.  **烂番茄 (Rotten Tomatoes):** 作为评分和补充信息来源。
    *   **匹配策略：**
        *   使用提取出的标题、年份、季号（如果适用）进行精准搜索。
        *   **高置信度匹配：** 只有当搜索结果与解析出的标题高度相似（考虑大小写、标点符号、常见缩写等），年份精确匹配，且媒体类型（电影/电视剧/番剧）一致时，才认定为准确匹配。
        *   **唯一性原则：** 如果搜索结果包含多个条目，选择与文件名信息（特别是年份、版本、季集号）最匹配的**唯一**条目。
        *   **模糊匹配回退：** 如果精准匹配失败，可以尝试进行轻微的模糊匹配（例如移除副标题、尝试常见缩写），但需降低置信度。
        *   **无法匹配的处理：** 如果无法找到高置信度的匹配项，则该条目的元数据字段应为空或 null。

**输出格式要求：**
*   输出必须是严格的JSON格式，且只包含JSON内容，不附带任何解释、说明或额外文本。
*   根元素必须是一个JSON数组 `[]`。
*   数组的每个元素都是一个JSON对象，代表一个文件名的解析结果。
*   JSON结构如下：
    ```json
    [
      {
        "file_name": "string",
        "title": "string",            // 中文标题（优先），如无中文则使用英文标题
        "original_title": "string",   // 媒体的原始语言标题 (如日文, 韩文等，非中英文)
        "year": "string",             // 发行年份
        "media_type": "string",       // "movie", "tv_show", "anime"
        "tmdb_id": "string",          // TMDB ID
        "imdb_id": "string",          // IMDb ID
        "anidb_id": "string",         // AniDB ID (如果适用)
        "douban_id": "string",        // 豆瓣 ID (如果适用)
        "season": "number | null",    // 文件名解析出的季号
        "episode": "number | null"    // 文件名解析出的集号
      }
    ]
    ```
*   **字段说明：**
    *   `file_name`: 原始文件名。
    *   `title`: **优先使用中文标题**。如果数据库有中文标题，必须使用中文；如果没有中文标题，则使用英文标题。
    *   `original_title`: 媒体在原产地的原始语言标题 (例如，日剧的日文标题，韩剧的韩文标题)。如果是中文作品或与 `title` 相同，则使用空字符串 `""`。
    *   `year`: 电影/电视剧/番剧的发行年份。
    *   `media_type`: 识别出的媒体类型，只能是 `"movie"`, `"tv_show"`, `"anime"` 之一。
    *   `tmdb_id`, `imdb_id`, `anidb_id`, `douban_id`: 对应数据库的唯一ID。如果未找到或不适用，请使用空字符串 `""`。
*   **值约定：**
    *   字符串字段（`title`, `original_title`, `year`, `media_type`, `tmdb_id` 等）如果信息缺失或无法准确识别，请使用空字符串 `""`。
    *   数字字段（`season`, `episode`）如果信息缺失或不适用，请使用 `null`。
    *   **严格性要求：** 任何时候都不要在JSON输出中包含额外的文本、解释或代码块标记（如 ```json）。
"""


# 智能文件分组提示词模板 - 简化版
# 用于将相关的媒体文件进行智能分组，如系列电影、电视剧集等
MAGIC_PROMPT = """
你是一个专业的影视文件分析专家。请分析以下文件列表，根据文件名将相关文件分组。

⚠️ **严格警告**：只有主标题相同或高度相似的文件才能分组！

🚫 **绝对禁止的错误分组**：
- ❌ 不要将"海底小纵队"、"疯狂元素城"、"蓝精灵"分在一组
- ❌ 不要仅因为都是动画片就分组
- ❌ 不要仅因为都是迪士尼/皮克斯就分组
- ❌ 不要仅因为年份相近就分组
- ❌ 不要将完全不同的IP/品牌混合

📺 **电视剧命名格式严格要求**：
- ✅ 必须使用：`标题 (首播年份) S季数`
- ✅ 正确示例：SEAL Team (2017) S01, SEAL Team (2018) S02
- ❌ 禁止格式：SEAL Team S01, SEAL Team (Season 1), SEAL Team (S01), SEAL Team (2018-2019) S02

✅ **正确分组标准**：主标题必须相同或为同一系列的续集/前传

## 📋 文件名模式识别指南

### 🎬 常见文件名格式：
1. **电视剧格式**：
   - `标题 (年份) S01E01.mkv` → 间谍过家家 (2022) S01E01.mkv
   - `标题 第1季 第1集.mkv` → 180天重启计划 第1季 第1集.mkv
   - `Title S01E01.mkv` → SPY×FAMILY S01E01.mkv
   - `标题.S01E01.mkv` → 亲爱的公主病.S01E01.mkv
   - `标题 S01 E01.mkv` → 某剧 S01 E01.mkv

2. **电影系列格式**：
   - `标题1 (年份).mkv` + `标题2 (年份).mkv` → 同系列电影
   - `标题 第一部.mkv` + `标题 第二部.mkv` → 系列电影
   - `标题之副标题 (年份).mkv` → 系列电影

3. **特殊标识符**：
   - `{tmdb-123456}` → TMDB数据库ID，可忽略
   - `1080p`, `720p`, `4K` → 分辨率标识，可忽略
   - `x264`, `x265`, `HEVC` → 编码格式，可忽略
   - `GB`, `MB` → 文件大小，可忽略

### 🎯 分组规则：
1. **极其严格的系列判断标准**：
   - **主标题必须完全相同或为明确的续集关系**
   - 例如："蓝精灵"、"蓝精灵2"、"蓝精灵之圣诞颂歌"
   - 例如："功夫熊猫"、"功夫熊猫2"、"功夫熊猫3"
   - **绝对不允许不同IP混合**

2. **严格禁止的分组模式**：
   - ❌ 绝不按类型分组（动画片、动作片、喜剧片等）
   - ❌ 绝不按制作公司分组（迪士尼、皮克斯、梦工厂等）
   - ❌ 绝不按年份分组
   - ❌ 绝不按主题分组（超级英雄、公主、动物等）

3. **分组要求**：
   - 每组至少2个文件
   - 单个文件不分组
   - **宁可不分组，也不要错误分组**
   - **电视剧分季原则**：同一部剧的不同季应该分别分组，每季使用该季的首播年份
   - **电视剧命名格式严格要求**：
     * 绝对不允许：SEAL Team S01, SEAL Team (Season 1), SEAL Team (S01)
     * 绝对不允许：SEAL Team (2018-2019) S02（年份范围）
     * 必须使用：SEAL Team (2017) S01, SEAL Team (2018) S02（单一年份）

4. **命名规范**：
   - 电视剧：**必须使用** `标题 (首播年份) S季数` 格式
   - **严格要求**：每季都必须包含该季的首播年份，如 SEAL Team (2017) S01, SEAL Team (2018) S02
   - 电影系列：`标题系列 (年份范围)`
   - **系列完整性优先**：同一系列的所有电影应该放在一个组里
   - **重要**：宝可梦剧场版、名侦探柯南剧场版等长期系列应该全部放在一个组里，不要按年份分段
   - **文件数量不是限制**：即使有20-30个文件也应该保持系列完整性

5. **具体禁止示例**：
   - ❌ "海底小纵队" + "蓝精灵" = 错误！完全不同的IP
   - ❌ "疯狂元素城" + "蓝精灵" = 错误！完全不同的IP
   - ❌ "冰雪奇缘" + "魔发奇缘" = 错误！虽然都是迪士尼公主片但不是同一系列
   - ✅ "蓝精灵" + "蓝精灵2" = 正确！同一系列的续集

### 💡 正确分析示例：
**示例1 - 电视剧正确分组**：
- `SEAL Team S01E01.mkv` (ID: 101)
- `SEAL Team S01E02.mkv` (ID: 102)
- `SEAL Team S02E01.mkv` (ID: 103)
- `SEAL Team S02E02.mkv` (ID: 104)

**✅ 正确分组**：必须包含年份，格式统一
```json
[
  {"group_name": "SEAL Team (2017) S01", "fileIds": [101, 102]},
  {"group_name": "SEAL Team (2018) S02", "fileIds": [103, 104]}
]
```

**❌ 错误的命名格式**：
```json
[
  {"group_name": "SEAL Team S01", "fileIds": [101, 102]},           // 缺少年份
  {"group_name": "SEAL Team (Season 1)", "fileIds": [101, 102]},   // 格式错误
  {"group_name": "SEAL Team (2017-2018) S01", "fileIds": [101, 102]}, // 年份范围错误
  {"group_name": "SEAL Team (S01)", "fileIds": [101, 102]}         // 格式错误
]
```

**示例2 - 电视剧正确分组**：
- `间谍过家家 (2022) S01E01.mkv` (ID: 123)
- `间谍过家家 (2022) S01E02.mkv` (ID: 124)
- `SPY×FAMILY S01E03.mkv` (ID: 125)
- `亲爱的公主病 (2016) S01E01.mkv` (ID: 126)

**正确分析**：识别"间谍过家家"和"SPY×FAMILY"为同一系列（不同语言），"亲爱的公主病"为不同系列
```json
[{"group_name": "间谍过家家 (2022) S01", "fileIds": [123, 124, 125]}]
```

**示例2 - 错误分组警示**：
- `蓝精灵2 (2013).mkv` (ID: 201)
- `蓝精灵之圣诞颂歌 (2011).mkv` (ID: 202)
- `海底小纵队：洞穴大冒险 (2020).mp4` (ID: 203)
- `疯狂元素城 (2023).mp4` (ID: 204)

**❌ 绝对错误的分组**：
```json
[{"group_name": "蓝精灵系列 (2011-2017)", "fileIds": [201, 202, 203, 204]}]
```
这是错误的！海底小纵队和疯狂元素城与蓝精灵完全无关！

**✅ 正确分组**：只将真正相关的文件分组
```json
[{"group_name": "蓝精灵系列 (2011-2013)", "fileIds": [201, 202]}]
```

**示例3 - 更多错误分组警示**：
- `冰雪奇缘 (2013).mkv` (ID: 301)
- `魔发奇缘 (2010).mkv` (ID: 302)
- `海洋奇缘 (2016).mkv` (ID: 303)

**❌ 错误**：将迪士尼公主电影分在一组
**✅ 正确**：不分组（它们是不同的独立电影）

**示例4 - 剧场版系列正确分组**：
- `宝可梦剧场版：七夜的许愿星 基拉祈 (2003).mkv` (ID: 401)
- `宝可梦剧场版：裂空的访问者 代欧奇希斯 (2004).mkv` (ID: 402)
- `宝可梦剧场版：梦幻与波导的勇者 路卡利欧 (2005).mkv` (ID: 403)
- `宝可梦剧场版：帝牙卢卡VS帕路奇亚VS达克莱伊 (2007).mkv` (ID: 404)
- `宝可梦剧场版：阿尔宙斯 超克的时空 (2009).mkv` (ID: 405)

**✅ 正确分组**：所有宝可梦剧场版应该放在一个组里
```json
[{"group_name": "宝可梦剧场版系列 (1998-2020)", "fileIds": [401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424]}]
```

**❌ 错误的年份分段**：
```json
[
  {"group_name": "宝可梦剧场版 (1998-2002)", "fileIds": [401, 402, 403, 404, 405]},
  {"group_name": "宝可梦剧场版 (2003-2007)", "fileIds": [406, 407, 408, 409, 410]},
  {"group_name": "宝可梦剧场版 (2008-2012)", "fileIds": [411, 412, 413, 414, 415]}
]
```
这是错误的！不要按年份分段！

**核心原则**：主标题必须相同，系列完整性优先于年份分段！

### 📝 输出格式：
```json
[
  {
    "group_name": "间谍过家家 (2022) S01",
    "fileIds": [文件ID1, 文件ID2, 文件ID3]
  },
  {
    "group_name": "复仇者联盟系列 (2012-2019)",
    "fileIds": [文件ID4, 文件ID5]
  }
]
```

### ⚠️ 最终警告：
- **只有主标题相同的文件才能分组！**
- **绝对禁止将不同IP/品牌的作品分在一组！**
- **绝对禁止按类型、公司、年份、主题分组！**
- **同一系列的所有文件应该放在一个组里（如所有宝可梦剧场版）！**
- 必须返回完整的JSON格式
- fileIds数组必须包含所有相关文件的ID
- 如果没有可分组的文件，返回 []
- 只返回JSON，不要其他文字说明
- **宁可返回空数组[]，也不要错误分组！**
- **再次强调：海底小纵队、疯狂元素城、蓝精灵是完全不同的IP，绝不能分在一组！**
- **宝可梦剧场版系列应该全部放在一个组里，不要按年份分段！**
- **名侦探柯南剧场版、蜡笔小新剧场版等长期系列也应该全部放在一个组里！**
- **绝对不要因为文件数量多就按年份分段！系列完整性最重要！**
- **电视剧命名格式必须严格统一：标题 (首播年份) S季数！**
- **绝对禁止的电视剧格式：SEAL Team S01, SEAL Team (Season 1), SEAL Team (S01), SEAL Team (2018-2019) S02！**
- **必须使用的正确格式：SEAL Team (2017) S01, SEAL Team (2018) S02, SEAL Team (2019) S03！**

"""
# 智能分组合并提示词模板
GROUP_MERGE_PROMPT = """你是一个专业的影视分类专家。分析提供的分组列表，判断哪些分组属于同一系列应该合并。

重要规则 - 绝对不能违反：
1. 绝对不要将电影与电视剧集合并 - 它们是完全不同的内容类型
2. 绝对不要将剧场版电影与电视剧合并，即使是同一IP
3. 绝对不要合并不同的系列，即使看起来相似
4. 绝对不要仅基于类型相似性合并（如所有恐怖片、所有喜剧）
5. **绝对不要将不同季的电视剧合并** - 每季应该保持独立
6. 只有在文件真正属于同一连续系列且内容类型相同时才合并

有效合并标准：
- 同一电影系列的续集/前传（如指环王1,2,3）
- **同一电视剧的同一季内的不同集** - 注意：不同季绝对不能合并
- 同一系列的不同电影（如宝可梦电影系列）
- 同一作品的重制版/导演剪辑版

**特别强调**：
- 老友记 S01 和 老友记 S02 是不同季，绝对不能合并
- 权力的游戏 S01 和 权力的游戏 S02 是不同季，绝对不能合并
- 每季应该保持独立的分组

**输出格式要求**：
必须返回标准JSON格式，不要添加任何解释文字。

```json
{
  "merges": [
    {
      "merged_name": "包含年份的系列名称",
      "groups_to_merge": ["分组1", "分组2"],
      "reason": "合并原因"
    }
  ]
}
```

**重要**：
1. 只返回JSON对象，不要其他内容。如果没有需要合并的分组，返回空的merges数组。
2. **merged_name必须包含年份信息**，格式要求：
   - 电视剧同季内合并："{标题} ({年份}) S{季数}" 例如："权力的游戏 (2011) S01"
   - 电影系列："{标题}系列 ({年份范围})" 例如："复仇者联盟系列 (2012-2019)"
3. **绝对禁止**：不要创建跨季合并，如"老友记 (1994) S01-S10"这样的格式

If no valid merges found, return: {"merges": []}"""


# ================================
# 全局配置和变量定义
# ================================

# 应用程序配置字典，包含所有可配置参数的默认值
app_config = {
    # 性能配置 - 优化预览刮削性能
    "QPS_LIMIT": 8,          # API请求频率限制（每秒请求数）- 提高到12以改善性能
    "CHUNK_SIZE": 50,         # 批量处理时的分块大小 - 减少到25以提高并发度
    "MAX_WORKERS": 6,         # 最大并发工作线程数 - 增加到6以提高并发处理能力

    # 123云盘API配置
    "CLIENT_ID": "",           # 123云盘开放平台客户端ID
    "CLIENT_SECRET": "",       # 123云盘开放平台客户端密钥

    # 第三方API配置
    "TMDB_API_KEY": "",        # The Movie Database API密钥
    "AI_API_KEY": "",          # AI API密钥（支持OpenAI兼容接口）
    "AI_API_URL": "",          # AI API服务地址（支持OpenAI兼容接口）

    # AI模型配置
    "MODEL": "",               # 默认AI模型名称
    "GROUPING_MODEL": "",      # 智能分组专用AI模型名称

    # 本地化配置
    "LANGUAGE": "zh-CN",       # 界面语言设置

    # 重试和超时配置
    "API_MAX_RETRIES": 3,      # API调用最大重试次数
    "API_RETRY_DELAY": 2,      # API重试等待时间（秒）
    "AI_API_TIMEOUT": 60,      # AI API调用超时时间（秒）
    "AI_MAX_RETRIES": 3,       # AI调用最大重试次数
    "AI_RETRY_DELAY": 2,       # AI重试等待时间（秒）
    "TMDB_API_TIMEOUT": 60,    # TMDB API调用超时时间（秒）
    "TMDB_MAX_RETRIES": 3,     # TMDB API最大重试次数
    "TMDB_RETRY_DELAY": 2,     # TMDB API重试等待时间（秒）
    "CLOUD_API_MAX_RETRIES": 3, # 123云盘API最大重试次数
    "CLOUD_API_RETRY_DELAY": 2, # 123云盘API重试等待时间（秒）
    "GROUPING_MAX_RETRIES": 3, # 智能分组最大重试次数（减少API调用）
    "GROUPING_RETRY_DELAY": 2, # 智能分组重试等待时间（秒）
    "TASK_QUEUE_GET_TIMEOUT": 1.0, # 任务队列获取超时时间（秒）

    # 质量评估配置
    "ENABLE_QUALITY_ASSESSMENT": False,  # 智能分组是否启用质量评估（禁用可提高性能）
    "ENABLE_SCRAPING_QUALITY_ASSESSMENT": True,  # 刮削功能是否启用质量评估（建议开启）

    # 端口管理配置
    "KILL_OCCUPIED_PORT_PROCESS": True  # 是否自动结束占用端口的进程（启用可避免端口冲突）
}

# ================================
# 全局变量声明
# ================================

# 日志队列，用于Web界面实时显示日志
log_queue = deque(maxlen=5000)

# 性能配置全局变量
QPS_LIMIT = app_config["QPS_LIMIT"]
CHUNK_SIZE = app_config["CHUNK_SIZE"]
MAX_WORKERS = app_config["MAX_WORKERS"]

# 123云盘API配置全局变量
CLIENT_ID = app_config["CLIENT_ID"]
CLIENT_SECRET = app_config["CLIENT_SECRET"]

# 第三方API配置全局变量
TMDB_API_KEY = ""
AI_API_KEY = ""
AI_API_URL = ""

# AI模型配置全局变量
MODEL = app_config["MODEL"]
GROUPING_MODEL = app_config["GROUPING_MODEL"]

# 本地化配置全局变量
LANGUAGE = app_config["LANGUAGE"]

# 质量评估配置全局变量
ENABLE_QUALITY_ASSESSMENT = app_config["ENABLE_QUALITY_ASSESSMENT"]  # 智能分组质量评估
ENABLE_SCRAPING_QUALITY_ASSESSMENT = app_config["ENABLE_SCRAPING_QUALITY_ASSESSMENT"]  # 刮削质量评估

# 123云盘API基础URL
BASE_API_URL = "https://open-api.123pan.com"

# API请求头模板
API_HEADERS = {
    "Content-Type": "application/json",
    "Platform": "open_platform",
    "Authorization": ""
}

# 支持的媒体文件扩展名列表
SUPPORTED_MEDIA_TYPES = [
    "wma", "wav", "mp3", "aac", "ra", "ram", "mp2", "ogg", "aif",
    "mpega", "amr", "mid", "midi", "m4a", "m4v", "wmv", "rmvb",
    "mpeg4", "mpeg2", "flv", "avi", "3gp", "mpga", "qt", "rm",
    "wmz", "wmd", "wvx", "wmx", "wm", "swf", "mpg", "mp4", "mkv",
    "mpeg", "mov", "mdf", "asf", "webm", "ogv", "m2ts", "ts", "vob",
    "divx", "xvid", "f4v", "m2v", "amv", "drc", "evo", "flc",
    "h264", "h265", "icod", "mod", "tod", "mts", "ogm", "qtff",
    "rec", "vp6", "vp7", "vp8", "vp9", "iso"
]



# 访问令牌（在应用启动时初始化）
access_token = None
access_token_expires_at = None  # 访问令牌过期时间

# 日志处理器全局变量
root_logger = None
file_handler = None
console_handler = None
queue_handler = None

# QPS限制器全局变量（在应用启动时初始化）
qps_limiter = None
v2_list_limiter = None
rename_limiter = None
move_limiter = None
delete_limiter = None

# 任务取消控制全局变量
current_task_cancelled = False
current_task_id = None

# ================================
# 缓存系统初始化（使用LRU缓存）
# ================================

# 路径缓存（小容量，中期有效）
folder_path_cache = LRUCache(max_size=500, ttl=1800)  # 30分钟
folder_path_cache._cache_name = 'folder_path_cache'

# 智能分组缓存（中等容量，短期有效）
grouping_cache = LRUCache(max_size=200, ttl=300)  # 5分钟
grouping_cache._cache_name = 'grouping_cache'

# 文件刮削结果缓存（大容量，短期有效）
scraping_cache = LRUCache(max_size=1000, ttl=600)  # 10分钟
scraping_cache._cache_name = 'scraping_cache'

# 目录内容缓存（中等容量，极短期有效）
folder_content_cache = LRUCache(max_size=300, ttl=180)  # 3分钟
folder_content_cache._cache_name = 'folder_content_cache'

# 保留原有的常量定义以兼容现有代码（调整为更短的缓存时间）
GROUPING_CACHE_DURATION = 300  # 5分钟
SCRAPING_CACHE_DURATION = 600  # 10分钟
FOLDER_CONTENT_CACHE_DURATION = 180  # 3分钟


def cleanup_all_caches():
    """
    清理所有缓存中的过期条目

    Returns:
        dict: 清理统计信息
    """
    stats = {}

    try:
        stats['folder_path_cache'] = folder_path_cache.cleanup_expired()
        stats['grouping_cache'] = grouping_cache.cleanup_expired()
        stats['scraping_cache'] = scraping_cache.cleanup_expired()
        stats['folder_content_cache'] = folder_content_cache.cleanup_expired()

        total_cleaned = sum(stats.values())
        if total_cleaned > 0:
            logging.info(f"🧹 清理了 {total_cleaned} 个过期缓存条目: {stats}")

        return stats
    except Exception as e:
        logging.error(f"❌ 缓存清理失败: {e}")
        return {}


def clear_operation_related_caches(folder_id=None, operation_type="unknown"):
    """
    清理与操作相关的缓存

    Args:
        folder_id: 操作的文件夹ID
        operation_type: 操作类型（scraping, renaming, grouping等）
    """
    try:
        cleared_count = 0

        if operation_type in ["scraping", "renaming"]:
            # 刮削和重命名操作需要清理刮削缓存
            old_size = scraping_cache.size()
            scraping_cache.clear()
            cleared_count += old_size
            logging.info(f"🧹 清理刮削缓存: {old_size} 项")

        if operation_type in ["renaming", "grouping"]:
            # 重命名和分组操作需要清理分组缓存
            old_size = grouping_cache.size()
            grouping_cache.clear()
            cleared_count += old_size
            logging.info(f"🧹 清理分组缓存: {old_size} 项")

        if folder_id:
            # 清理特定文件夹的内容缓存
            folder_content_cache.delete(f"folder_{folder_id}")
            cleared_count += 1
            logging.info(f"🧹 清理文件夹 {folder_id} 的内容缓存")

        if operation_type == "major_change":
            # 重大变更时清理所有缓存
            stats = cleanup_all_caches()
            cleared_count += sum(stats.values())

        if cleared_count > 0:
            logging.info(f"🧹 操作 {operation_type} 触发缓存清理，共清理 {cleared_count} 项")

        return cleared_count
    except Exception as e:
        logging.error(f"❌ 操作相关缓存清理失败: {e}")
        return 0


def start_cache_cleanup_task():
    """启动缓存清理后台任务"""
    def cache_cleanup_worker():
        while True:
            try:
                time.sleep(180)  # 每3分钟清理一次（更频繁）
                cleanup_all_caches()
            except Exception as e:
                logging.error(f"❌ 缓存清理任务异常: {e}")
                time.sleep(60)  # 出错后等待1分钟再重试

    cleanup_thread = threading.Thread(target=cache_cleanup_worker, daemon=True)
    cleanup_thread.start()
    logging.info("🧹 缓存清理后台任务已启动（每3分钟清理一次）")

# 🚦 请求限流控制全局变量（已优化为与任务队列配合）
folder_request_tracker = {}
FOLDER_REQUEST_LIMIT_DURATION = 30  # 限流时间窗口：30秒（减少，因为有任务队列保护）
MAX_REQUESTS_PER_FOLDER = 1  # 每个文件夹在时间窗口内的最大请求数

# 🚀 任务队列配置
TASK_QUEUE_MAX_SIZE = 10  # 最大队列大小
TASK_TIMEOUT_SECONDS = 300  # 任务超时时间（5分钟）

# ================================
# 重试和超时配置全局变量（从配置文件读取）
# ================================

# API重试配置
API_MAX_RETRIES = 3  # API调用最大重试次数
API_RETRY_DELAY = 2  # API重试等待时间（秒）

# AI API配置
AI_API_TIMEOUT = 60  # AI API调用超时时间（秒）
AI_MAX_RETRIES = 3  # AI调用最大重试次数
AI_RETRY_DELAY = 2  # AI重试等待时间（秒）

# TMDB API配置
TMDB_API_TIMEOUT = 60  # TMDB API调用超时时间（秒）
TMDB_MAX_RETRIES = 3  # TMDB API最大重试次数
TMDB_RETRY_DELAY = 2  # TMDB API重试等待时间（秒）

# 123云盘API配置
CLOUD_API_MAX_RETRIES = 3  # 123云盘API最大重试次数
CLOUD_API_RETRY_DELAY = 2  # 123云盘API重试等待时间（秒）

# 智能分组重试配置
GROUPING_MAX_RETRIES = 3  # 智能分组最大重试次数
GROUPING_RETRY_DELAY = 2  # 智能分组重试等待时间（秒）

# 任务队列超时配置
TASK_QUEUE_GET_TIMEOUT = 1.0  # 任务队列获取超时时间（秒）

# ================================
# 全局任务队列管理系统
# ================================

import queue
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import uuid

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消
    TIMEOUT = "timeout"      # 超时

@dataclass
class GroupingTask:
    """智能分组任务数据类"""
    task_id: str
    folder_id: str
    folder_name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0  # 进度百分比 0-100

    def get_duration(self) -> Optional[float]:
        """获取任务执行时长"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return None

class GroupingTaskManager:
    """智能分组任务管理器"""

    def __init__(self, max_queue_size: int = 10, task_timeout: int = 300):
        self.task_queue = queue.Queue(maxsize=max_queue_size)
        self.active_tasks: Dict[str, GroupingTask] = {}
        self.completed_tasks: Dict[str, GroupingTask] = {}
        self.max_completed_tasks = 50  # 最多保留50个已完成任务
        self.task_timeout = task_timeout  # 任务超时时间（秒）
        self.lock = threading.RLock()
        self.worker_thread = None
        self.is_running = False
        self._start_worker()

    def _start_worker(self):
        """启动工作线程"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logging.info("🚀 智能分组任务管理器已启动")

    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 从队列中获取任务（阻塞等待）
                task = self.task_queue.get(timeout=TASK_QUEUE_GET_TIMEOUT)
                if task is None:  # 停止信号
                    break

                self._execute_task(task)
                self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"❌ 任务管理器工作线程异常: {e}")

    def _execute_task(self, task: GroupingTask):
        """执行单个任务"""
        with self.lock:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self.active_tasks[task.task_id] = task

        logging.info(f"🎯 开始执行智能分组任务: {task.task_id} (文件夹: {task.folder_name})")

        # 创建超时检查线程
        timeout_thread = threading.Thread(target=self._check_task_timeout, args=(task,), daemon=True)
        timeout_thread.start()

        try:
            # 检查任务是否已被取消
            if task.status == TaskStatus.CANCELLED:
                return

            # 执行实际的分组任务
            result = self._perform_grouping_analysis(task)

            with self.lock:
                if task.status not in [TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    task.result = result
                    task.progress = 100.0

                    # 移动到已完成任务
                    self._move_to_completed(task)

                    logging.info(f"✅ 智能分组任务完成: {task.task_id} (耗时: {task.get_duration():.2f}秒)")

        except Exception as e:
            with self.lock:
                if task.status not in [TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.error = str(e)
                    self._move_to_completed(task)

                    logging.error(f"❌ 智能分组任务失败: {task.task_id} - {e}")

    def _check_task_timeout(self, task: GroupingTask):
        """检查任务超时"""
        time.sleep(self.task_timeout)

        with self.lock:
            if task.task_id in self.active_tasks and task.status == TaskStatus.RUNNING:
                # 任务超时
                task.status = TaskStatus.TIMEOUT
                task.completed_at = time.time()
                task.error = f"任务执行超时 (超过 {self.task_timeout} 秒)"
                self._move_to_completed(task)

                logging.warning(f"⏰ 智能分组任务超时: {task.task_id} (超时时间: {self.task_timeout}秒)")

    def _perform_grouping_analysis(self, task: GroupingTask) -> Dict[str, Any]:
        """执行实际的分组分析"""
        # 检查任务是否已被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        # 设置当前任务ID，以便全局取消机制能够工作
        global current_task_id, current_task_cancelled
        current_task_id = task.task_id
        current_task_cancelled = False  # 重置取消标志

        # 这里调用现有的分组分析函数
        video_files = []
        get_video_files_recursively(task.folder_id, video_files)

        # 再次检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        if not video_files:
            return {
                'success': False,
                'error': '文件夹中没有找到视频文件',
                'movie_info': [],
                'count': 0,
                'size': '0GB'
            }

        # 更新进度
        task.progress = 30.0

        # 调用分组分析
        def progress_callback(message):
            # 检查任务是否被取消
            if task.status == TaskStatus.CANCELLED:
                raise Exception("任务已被取消")

            # 详细的进度更新逻辑
            if '开始智能文件分组分析' in message:
                task.progress = 40.0
                logging.info(f"🎯 智能分组进度: {task.progress}% - {message}")
            elif '按子文件夹分组' in message:
                task.progress = 45.0
                logging.info(f"📁 智能分组进度: {task.progress}% - {message}")
            elif '处理子文件夹' in message:
                task.progress = min(50.0 + (task.progress - 50.0) * 0.1, 85.0)
                logging.info(f"🔄 智能分组进度: {task.progress}% - {message}")
            elif 'AI分组耗时' in message:
                task.progress = min(task.progress + 5.0, 85.0)
                logging.info(f"⏱️ 智能分组进度: {task.progress}% - {message}")
            elif '分组分析完成' in message:
                task.progress = 90.0
                logging.info(f"✅ 智能分组进度: {task.progress}% - {message}")

        # 检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        grouping_result = get_folder_grouping_analysis_internal(video_files, task.folder_id, progress_callback)

        # 最后检查任务是否被取消
        if task.status == TaskStatus.CANCELLED:
            raise Exception("任务已被取消")

        return {
            'success': True,
            'movie_info': grouping_result.get('movie_info', []),
            'video_files': video_files,
            'count': len(video_files),
            'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB"
        }

    def _move_to_completed(self, task: GroupingTask):
        """将任务移动到已完成列表"""
        if task.task_id in self.active_tasks:
            del self.active_tasks[task.task_id]

        self.completed_tasks[task.task_id] = task

        # 清理过多的已完成任务
        if len(self.completed_tasks) > self.max_completed_tasks:
            # 删除最旧的任务
            oldest_task_id = min(self.completed_tasks.keys(),
                                key=lambda tid: self.completed_tasks[tid].completed_at or 0)
            del self.completed_tasks[oldest_task_id]

    def submit_task(self, folder_id: str, folder_name: str) -> str:
        """提交新的分组任务"""
        task_id = str(uuid.uuid4())
        task = GroupingTask(
            task_id=task_id,
            folder_id=str(folder_id),
            folder_name=folder_name
        )

        try:
            with self.lock:
                # 检查是否已有相同文件夹的任务在队列中或执行中
                for existing_task in list(self.active_tasks.values()):
                    if existing_task.folder_id == str(folder_id) and existing_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                        raise ValueError(f"文件夹 {folder_name} 已有分组任务在进行中")

                # 检查队列中是否有相同文件夹的任务
                temp_queue = []
                while not self.task_queue.empty():
                    try:
                        queued_task = self.task_queue.get_nowait()
                        if queued_task.folder_id == str(folder_id):
                            raise ValueError(f"文件夹 {folder_name} 已有分组任务在队列中")
                        temp_queue.append(queued_task)
                    except queue.Empty:
                        break

                # 重新放回队列中的任务
                for queued_task in temp_queue:
                    self.task_queue.put_nowait(queued_task)

                # 添加新任务到队列和活动任务列表
                self.task_queue.put_nowait(task)
                self.active_tasks[task_id] = task  # 立即添加到活动任务列表
                logging.info(f"📝 智能分组任务已提交: {task_id} (文件夹: {folder_name})")

                return task_id

        except queue.Full:
            raise ValueError("任务队列已满，请稍后再试")

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                    self._move_to_completed(task)
                    logging.info(f"🛑 智能分组任务已取消: {task_id}")
                    return True
            return False

    def get_task_status(self, task_id: str) -> Optional[GroupingTask]:
        """获取任务状态"""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            return None

    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        with self.lock:
            return {
                'queue_size': self.task_queue.qsize(),
                'active_tasks': len(self.active_tasks),
                'completed_tasks': len(self.completed_tasks),
                'is_running': self.is_running
            }

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        with self.lock:
            to_remove = []
            for task_id, task in self.completed_tasks.items():
                if (task.completed_at or task.created_at) < cutoff_time:
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self.completed_tasks[task_id]

            if to_remove:
                logging.info(f"🧹 清理了 {len(to_remove)} 个旧的分组任务")

    def get_health_status(self) -> Dict[str, Any]:
        """获取任务管理器健康状态"""
        with self.lock:
            # 检查是否有长时间运行的任务
            long_running_tasks = []
            current_time = time.time()

            for task in self.active_tasks.values():
                if task.started_at and (current_time - task.started_at) > (self.task_timeout * 0.8):
                    long_running_tasks.append({
                        'task_id': task.task_id,
                        'folder_name': task.folder_name,
                        'running_time': current_time - task.started_at
                    })

            return {
                'is_healthy': len(long_running_tasks) == 0 and self.is_running,
                'worker_running': self.is_running,
                'queue_size': self.task_queue.qsize(),
                'active_tasks_count': len(self.active_tasks),
                'completed_tasks_count': len(self.completed_tasks),
                'long_running_tasks': long_running_tasks,
                'max_queue_size': self.task_queue.maxsize,
                'task_timeout': self.task_timeout
            }

    def restart_worker_if_needed(self):
        """如果工作线程停止，重新启动它"""
        if not self.is_running or not self.worker_thread or not self.worker_thread.is_alive():
            logging.warning("🔄 检测到工作线程停止，正在重新启动...")
            self.is_running = False
            self._start_worker()

    def force_cleanup_stuck_tasks(self):
        """强制清理卡住的任务"""
        current_time = time.time()
        stuck_tasks = []

        with self.lock:
            for task_id, task in list(self.active_tasks.items()):
                if task.started_at and (current_time - task.started_at) > (self.task_timeout * 1.5):
                    # 任务运行时间超过超时时间的1.5倍，认为是卡住了
                    task.status = TaskStatus.TIMEOUT
                    task.completed_at = current_time
                    task.error = f"任务被强制清理 (运行时间: {current_time - task.started_at:.1f}秒)"
                    self._move_to_completed(task)
                    stuck_tasks.append(task_id)

        if stuck_tasks:
            logging.warning(f"🧹 强制清理了 {len(stuck_tasks)} 个卡住的任务: {stuck_tasks}")

        return len(stuck_tasks)

# 全局任务管理器实例
try:
    grouping_task_manager = GroupingTaskManager(
        max_queue_size=TASK_QUEUE_MAX_SIZE,
        task_timeout=TASK_TIMEOUT_SECONDS
    )
    logging.info("✅ 智能分组任务管理器已成功初始化")
except Exception as e:
    logging.error(f"❌ 任务管理器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    grouping_task_manager = None

# ================================
# 任务管理器维护功能
# ================================

def start_task_manager_maintenance():
    """启动任务管理器维护线程"""
    def maintenance_worker():
        while True:
            try:
                # 每5分钟执行一次维护
                time.sleep(300)

                # 检查并重启工作线程
                grouping_task_manager.restart_worker_if_needed()

                # 清理旧任务（每小时执行一次）
                if int(time.time()) % 3600 < 300:  # 在每小时的前5分钟内执行
                    grouping_task_manager.cleanup_old_tasks(24)

                # 强制清理卡住的任务
                stuck_count = grouping_task_manager.force_cleanup_stuck_tasks()
                if stuck_count > 0:
                    logging.warning(f"🧹 维护任务清理了 {stuck_count} 个卡住的任务")

                # 记录健康状态
                health = grouping_task_manager.get_health_status()
                if not health['is_healthy']:
                    logging.warning(f"⚠️ 任务管理器健康状态异常: {health}")

            except Exception as e:
                logging.error(f"❌ 任务管理器维护失败: {e}")

    # 启动维护线程
    maintenance_thread = threading.Thread(target=maintenance_worker, daemon=True)
    maintenance_thread.start()
    logging.info("🔧 任务管理器维护线程已启动")

# 启动维护线程
start_task_manager_maintenance()

# ================================
# 任务管理API端点
# ================================

@app.route('/api/grouping_task/submit', methods=['POST'])
def submit_grouping_task():
    """提交智能分组任务到队列"""
    try:
        # 检查任务管理器是否可用
        if grouping_task_manager is None:
            return jsonify({'success': False, 'error': '任务管理器未初始化，请检查系统状态'})

        folder_id_str = request.form.get('folder_id', '0')
        folder_name = request.form.get('folder_name', '未知文件夹')

        # 验证文件夹ID
        folder_id, error_msg = validate_folder_id(folder_id_str)
        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        # 提交任务到队列
        task_id = grouping_task_manager.submit_task(folder_id, folder_name)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'智能分组任务已提交到队列 (任务ID: {task_id})'
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.error(f"提交智能分组任务失败: {e}")
        return jsonify({'success': False, 'error': f'提交任务失败: {str(e)}'})

@app.route('/api/grouping_task/status/<task_id>', methods=['GET'])
def get_grouping_task_status(task_id):
    """获取智能分组任务状态"""
    try:
        # 添加调试日志
        logging.info(f"🔍 前端轮询任务状态: {task_id}")

        task = grouping_task_manager.get_task_status(task_id)
        if not task:
            logging.warning(f"⚠️ 任务 {task_id} 不存在")
            return jsonify({'success': False, 'error': '任务不存在'})

        logging.info(f"📊 返回任务状态: {task.status.value}, 进度: {task.progress}%")
        return jsonify({
            'success': True,
            'task': {
                'task_id': task.task_id,
                'folder_id': task.folder_id,
                'folder_name': task.folder_name,
                'status': task.status.value,
                'progress': task.progress,
                'created_at': task.created_at,
                'started_at': task.started_at,
                'completed_at': task.completed_at,
                'duration': task.get_duration(),
                'result': task.result,
                'error': task.error
            }
        })

    except Exception as e:
        logging.error(f"获取任务状态失败: {e}")
        return jsonify({'success': False, 'error': f'获取任务状态失败: {str(e)}'})

@app.route('/api/grouping_task/queue_info', methods=['GET'])
def get_grouping_queue_info():
    """获取智能分组任务队列信息"""
    try:
        queue_info = grouping_task_manager.get_queue_info()

        # 获取当前活跃任务的详细信息
        active_tasks = []
        with grouping_task_manager.lock:
            for task in grouping_task_manager.active_tasks.values():
                active_tasks.append({
                    'task_id': task.task_id,
                    'folder_name': task.folder_name,
                    'status': task.status.value,
                    'progress': task.progress,
                    'duration': task.get_duration()
                })

        return jsonify({
            'success': True,
            'queue_info': queue_info,
            'active_tasks': active_tasks
        })

    except Exception as e:
        logging.error(f"获取队列信息失败: {e}")
        return jsonify({'success': False, 'error': f'获取队列信息失败: {str(e)}'})

@app.route('/api/grouping_task/cancel/<task_id>', methods=['POST'])
def cancel_grouping_task(task_id):
    """取消智能分组任务"""
    try:
        success = grouping_task_manager.cancel_task(task_id)
        if success:
            return jsonify({'success': True, 'message': f'任务 {task_id} 已取消'})
        else:
            return jsonify({'success': False, 'error': '任务不存在或无法取消'})

    except Exception as e:
        logging.error(f"取消任务失败: {e}")
        return jsonify({'success': False, 'error': f'取消任务失败: {str(e)}'})

@app.route('/api/grouping_task/health', methods=['GET'])
def get_grouping_task_health():
    """获取任务管理器健康状态"""
    try:
        health_status = grouping_task_manager.get_health_status()
        return jsonify({
            'success': True,
            'health': health_status
        })
    except Exception as e:
        logging.error(f"获取健康状态失败: {e}")
        return jsonify({'success': False, 'error': f'获取健康状态失败: {str(e)}'})

@app.route('/api/grouping_task/maintenance', methods=['POST'])
def perform_grouping_task_maintenance():
    """执行任务管理器维护操作"""
    try:
        action = request.form.get('action', '')

        if action == 'cleanup_old_tasks':
            max_age_hours = int(request.form.get('max_age_hours', 24))
            grouping_task_manager.cleanup_old_tasks(max_age_hours)
            return jsonify({'success': True, 'message': f'已清理超过 {max_age_hours} 小时的旧任务'})

        elif action == 'restart_worker':
            grouping_task_manager.restart_worker_if_needed()
            return jsonify({'success': True, 'message': '工作线程已重启'})

        elif action == 'force_cleanup_stuck':
            cleaned_count = grouping_task_manager.force_cleanup_stuck_tasks()
            return jsonify({'success': True, 'message': f'强制清理了 {cleaned_count} 个卡住的任务'})

        else:
            return jsonify({'success': False, 'error': '无效的维护操作'})

    except Exception as e:
        logging.error(f"执行维护操作失败: {e}")
        return jsonify({'success': False, 'error': f'执行维护操作失败: {str(e)}'})

def check_task_cancelled():
    """检查当前任务是否被取消"""
    # 使用app_state检查取消状态
    app_state.check_task_cancelled()

    # 检查任务队列中的取消状态
    if app_state.current_task_id and grouping_task_manager:
        task = grouping_task_manager.get_task_status(app_state.current_task_id)
        if task and task.status == TaskStatus.CANCELLED:
            logging.info(f"🛑 任务已被用户取消 (任务队列): {app_state.current_task_id}")
            raise TaskCancelledException("任务已被用户取消")

def cancel_current_task():
    """取消当前正在运行的任务"""
    app_state.cancel_task()

    # 同时取消任务队列中的任务
    if app_state.current_task_id:
        cancelled = grouping_task_manager.cancel_task(app_state.current_task_id)
        if cancelled:
            logging.info(f"🛑 用户请求取消当前任务: {app_state.current_task_id} (任务队列)")
        else:
            logging.warning(f"⚠️ 任务队列中未找到任务: {app_state.current_task_id}")

    logging.info("🛑 用户请求取消当前任务 (全局标志)")

def start_new_task(task_id=None):
    """开始新任务"""
    task_id = task_id or str(int(time.time()))
    app_state.start_task(task_id)

    # 清理路径缓存（避免内存泄漏）
    if folder_path_cache.size() > 1000:  # 缓存过多时清理
        folder_path_cache.clear()
        logging.info("🧹 清理路径缓存")

    # 清理目录内容缓存（避免内存泄漏）
    if folder_content_cache.size() > 500:  # 目录缓存过多时清理
        folder_content_cache.clear()
        logging.info("🧹 清理目录内容缓存")

    # 定期清理过期缓存
    cleanup_expired_folder_cache()

def reset_task_state():
    """重置任务状态（用于普通操作）"""
    app_state.current_task_id = None
    app_state.task_cancelled = False

# ================================
# 工具函数和辅助方法
# ================================

def validate_folder_id(folder_id):
    """
    验证并转换文件夹ID

    Args:
        folder_id: 待验证的文件夹ID（可能是字符串或数字）

    Returns:
        tuple: (转换后的整数ID, 错误信息)
               如果验证成功，返回 (int_id, None)
               如果验证失败，返回 (None, error_message)
    """
    if not folder_id or folder_id == 'null' or folder_id == 'undefined':
        return None, '无效的文件夹ID'

    try:
        return int(folder_id), None
    except (ValueError, TypeError):
        return None, '文件夹ID必须是数字'


def decode_jwt_token(token):
    """
    解析JWT token获取过期时间

    Args:
        token (str): JWT访问令牌

    Returns:
        dict or None: 包含过期时间等信息的字典，解析失败返回None
    """
    try:
        if not token:
            return None

        # JWT token由三部分组成，用.分隔：header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            logging.warning("⚠️ 访问令牌格式不正确，不是有效的JWT token")
            return None

        # 解析payload部分（第二部分）
        payload = parts[1]

        # JWT使用base64url编码，需要补齐padding
        missing_padding = len(payload) % 4
        if missing_padding:
            payload += '=' * (4 - missing_padding)

        # 解码payload
        decoded_bytes = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded_bytes.decode('utf-8'))

        return payload_data

    except Exception as e:
        logging.error(f"❌ 解析JWT token失败: {e}")
        return None


def is_access_token_expired(token=None):
    """
    检查访问令牌是否过期

    Args:
        token (str, optional): 要检查的访问令牌，如果不提供则使用全局token

    Returns:
        bool: True表示已过期或无效，False表示仍然有效
    """
    global access_token, access_token_expires_at

    check_token = token or access_token
    if not check_token:
        logging.warning("⚠️ 没有访问令牌可供检查")
        return True

    try:
        # 解析JWT token
        payload = decode_jwt_token(check_token)
        if not payload:
            logging.warning("⚠️ 无法解析访问令牌")
            return True

        # 获取过期时间（exp字段，Unix时间戳）
        exp_timestamp = payload.get('exp')
        if not exp_timestamp:
            logging.warning("⚠️ 访问令牌中没有过期时间信息")
            return True

        # 转换为datetime对象
        expires_at = datetime.datetime.fromtimestamp(exp_timestamp)
        current_time = datetime.datetime.now()

        # 更新全局过期时间变量
        if token is None:  # 只有检查全局token时才更新
            access_token_expires_at = expires_at

        # 检查是否过期（提前5分钟判断为过期，留出刷新时间）
        buffer_time = datetime.timedelta(minutes=5)
        is_expired = current_time >= (expires_at - buffer_time)

        if is_expired:
            logging.warning(f"⚠️ 访问令牌已过期或即将过期。过期时间: {expires_at}, 当前时间: {current_time}")
        else:
            # logging.info(f"✅ 访问令牌有效，剩余时间: {expires_at - current_time}")
            pass

        return is_expired

    except Exception as e:
        logging.error(f"❌ 检查访问令牌过期时间失败: {e}")
        return True


def refresh_access_token_if_needed():
    """
    如果访问令牌过期，自动刷新访问令牌

    Returns:
        bool: True表示令牌有效或刷新成功，False表示刷新失败
    """
    global access_token

    # 检查当前令牌是否过期
    if not is_access_token_expired():
        return True  # 令牌仍然有效

    logging.info("🔄 访问令牌已过期，尝试刷新...")

    # 尝试获取新的访问令牌
    if CLIENT_ID and CLIENT_SECRET:
        new_token = get_access_token_from_api(CLIENT_ID, CLIENT_SECRET)
        if new_token:
            # 更新全局变量
            access_token = new_token
            API_HEADERS["Authorization"] = f"Bearer {new_token}"

            # 保存到文件（Windows兼容性：指定UTF-8编码）
            try:
                with open("123_access_token.txt", "w", encoding='utf-8') as f:
                    f.write(new_token)
                logging.info("✅ 访问令牌刷新成功并已保存")
                return True
            except Exception as e:
                logging.error(f"❌ 保存新访问令牌失败: {e}")
                return True  # 令牌已更新，只是保存失败
        else:
            logging.error("❌ 无法获取新的访问令牌")
            return False
    else:
        logging.error("❌ 缺少CLIENT_ID或CLIENT_SECRET，无法刷新访问令牌")
        return False


def ensure_valid_access_token(func):
    """
    装饰器：确保API调用前访问令牌有效

    在调用需要访问令牌的API函数前，自动检查并刷新过期的令牌
    如果API调用返回令牌超限错误，会自动刷新令牌并重试
    """
    def wrapper(*args, **kwargs):
        global access_token
        max_retries = API_MAX_RETRIES  # 使用全局配置

        for attempt in range(max_retries):
            try:
                # 第一次调用前检查并刷新访问令牌
                if attempt == 0:
                    if not refresh_access_token_if_needed():
                        logging.error("❌ 访问令牌无效且无法刷新，API调用可能失败")

                # 调用原函数
                return func(*args, **kwargs)

            except TokenLimitExceededError as e:
                logging.warning(f"⚠️ 访问令牌使用次数超限 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # 强制刷新访问令牌
                    logging.info("🔄 强制刷新访问令牌...")
                    if CLIENT_ID and CLIENT_SECRET:
                        new_token = get_access_token_from_api(CLIENT_ID, CLIENT_SECRET)
                        if new_token:
                            access_token = new_token
                            API_HEADERS["Authorization"] = f"Bearer {new_token}"

                            # 保存到文件（Windows兼容性：指定UTF-8编码）
                            try:
                                with open("123_access_token.txt", "w", encoding='utf-8') as f:
                                    f.write(new_token)
                                logging.info("✅ 访问令牌强制刷新成功")
                            except Exception as save_e:
                                logging.error(f"❌ 保存新访问令牌失败: {save_e}")
                        else:
                            logging.error("❌ 无法获取新的访问令牌")
                            raise e  # 重新抛出异常
                    else:
                        logging.error("❌ 缺少CLIENT_ID或CLIENT_SECRET，无法刷新访问令牌")
                        raise e  # 重新抛出异常
                else:
                    # 最后一次重试失败，抛出异常
                    raise e

            except AccessTokenError as e:
                logging.warning(f"⚠️ 访问令牌认证错误 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    # 强制刷新访问令牌
                    logging.info("🔄 检测到401错误，强制刷新访问令牌...")
                    if CLIENT_ID and CLIENT_SECRET:
                        new_token = get_access_token_from_api(CLIENT_ID, CLIENT_SECRET)
                        if new_token:
                            access_token = new_token
                            API_HEADERS["Authorization"] = f"Bearer {new_token}"

                            # 保存到文件（Windows兼容性：指定UTF-8编码）
                            try:
                                with open("123_access_token.txt", "w", encoding='utf-8') as f:
                                    f.write(new_token)
                                logging.info("✅ 访问令牌强制刷新成功，将重试API调用")
                            except Exception as save_e:
                                logging.error(f"❌ 保存新访问令牌失败: {save_e}")
                        else:
                            logging.error("❌ 无法获取新的访问令牌")
                            raise e  # 重新抛出异常
                    else:
                        logging.error("❌ 缺少CLIENT_ID或CLIENT_SECRET，无法刷新访问令牌")
                        raise e  # 重新抛出异常
                else:
                    # 最后一次重试失败，抛出异常
                    logging.error(f"❌ 访问令牌刷新失败，已尝试 {max_retries} 次")
                    raise e

        # 如果所有重试都失败，调用原函数（让它处理错误）
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def call_ai_api(prompt, model=None, temperature=0.1):
    """
    调用AI API进行文本生成（支持OpenAI兼容接口）

    Args:
        prompt (str): 发送给AI的提示词
        model (str, optional): 使用的AI模型名称，默认使用配置中的模型
        temperature (float): 生成文本的随机性，0.0-1.0之间

    Returns:
        str or None: AI生成的文本内容，失败时返回None
    """
    try:
        # 检查必要的配置
        if not AI_API_KEY:
            logging.error("❌ AI API密钥未配置")
            return None

        if not AI_API_URL:
            logging.error("❌ AI API服务地址未配置")
            return None

        if not model:
            logging.error("❌ 模型名称未指定")
            return None

        logging.info(f"🌐 调用AI API: {AI_API_URL}")
        logging.info(f"🤖 使用模型: {model}")
        logging.info(f"📝 提示词长度: {len(prompt)} 字符")

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
            # "max_tokens": max_tokens
        }

        # 使用全局配置的超时时间
        response = requests.post(AI_API_URL, headers=headers, json=payload, timeout=AI_API_TIMEOUT)

        logging.info(f"📊 API响应状态码: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        # 检查响应格式
        if "choices" not in data:
            logging.error(f"❌ API响应格式错误，缺少choices字段: {data}")
            return None

        if not data["choices"] or len(data["choices"]) == 0:
            logging.error(f"❌ API响应choices为空: {data}")
            return None

        if "message" not in data["choices"][0]:
            logging.error(f"❌ API响应缺少message字段: {data['choices'][0]}")
            return None

        if "content" not in data["choices"][0]["message"]:
            logging.error(f"❌ API响应缺少content字段: {data['choices'][0]['message']}")
            return None

        content = data["choices"][0]["message"]["content"]
        logging.info(f"✅ AI API调用成功，返回内容长度: {len(content)} 字符")

        return content

    except requests.exceptions.Timeout as e:
        logging.error(f"❌ AI API调用超时: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"❌ AI API连接失败: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f"❌ AI API HTTP错误: {e}, 响应内容: {e.response.text if e.response else 'N/A'}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ AI API请求异常: {e}")
        return None
    except KeyError as e:
        logging.error(f"❌ AI API响应解析失败，缺少字段: {e}")
        return None
    except Exception as e:
        logging.error(f"❌ AI API调用未知错误: {e}")
        return None

def parse_json_from_ai_response(response_content):
    """
    从AI响应中解析JSON数据

    AI的响应可能包含额外的文本，此函数尝试提取其中的JSON部分

    Args:
        response_content (str): AI返回的原始响应内容

    Returns:
        dict or None: 解析成功返回字典对象，失败返回None
    """
    if not response_content:
        return None

    # 方法1: 尝试找到所有JSON块，使用第一个有效的
    json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)

    for json_str in json_matches:
        try:
            parsed_json = json.loads(json_str)
            # 验证JSON是否包含必要的字段
            if isinstance(parsed_json, dict) and 'suggested_name' in parsed_json:
                logging.info(f"✅ 成功解析JSON (方法1): {json_str[:100]}...")
                return parsed_json
        except json.JSONDecodeError:
            continue

    # 方法2: 使用贪婪匹配提取最大的JSON块
    json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
    if json_match:
        json_str = json_match.group()

        # 尝试修复常见的JSON格式问题
        # 移除重复的JSON块（如果存在）
        if '```json' in json_str:
            # 提取第一个```json块中的内容
            json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', json_str, re.DOTALL)
            if json_blocks:
                json_str = json_blocks[0]

        try:
            parsed_json = json.loads(json_str)
            logging.info(f"✅ 成功解析JSON (方法2): {json_str[:100]}...")
            return parsed_json
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {e}")
            logging.debug(f"原始JSON字符串: {json_str[:500]}...")

            # 方法3: 尝试修复常见的JSON错误
            try:
                # 移除可能的重复内容
                if json_str.count('{') > json_str.count('}'):
                    # 找到第一个完整的JSON对象
                    brace_count = 0
                    end_pos = 0
                    for i, char in enumerate(json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break

                    if end_pos > 0:
                        json_str = json_str[:end_pos]
                        parsed_json = json.loads(json_str)
                        logging.info(f"✅ 成功解析JSON (方法3): {json_str[:100]}...")
                        return parsed_json
            except json.JSONDecodeError:
                pass
    else:
        logging.error(f"响应中未找到JSON格式: {response_content[:200]}...")

    return None

def match_files_with_ai(group_name, video_files, used_file_ids, target_count):
    """
    使用AI进行智能文件匹配

    根据分组名称，让AI智能判断哪些文件应该属于该分组

    Args:
        group_name (str): 目标分组的名称
        video_files (list): 可用的视频文件列表
        used_file_ids (set): 已经被使用的文件ID集合
        target_count (int): 目标匹配的文件数量

    Returns:
        list: 匹配到的文件ID列表
    """
    try:
        # 准备可用的文件列表
        available_files = [f for f in video_files if f['fileId'] not in used_file_ids]

        if not available_files:
            return []

        # 限制文件数量，避免prompt过长
        max_files_for_ai = 50
        if len(available_files) > max_files_for_ai:
            available_files = available_files[:max_files_for_ai]

        # 构建文件列表字符串
        file_list = []
        for i, file_info in enumerate(available_files):
            file_list.append(f"{i}: {file_info['filename']}")

        files_text = "\n".join(file_list)

        # 构建AI匹配prompt
        match_prompt = f"""
        请分析以下文件列表，找出属于分组"{group_name}"的文件。

        文件列表：
        {files_text}

        请根据文件名判断哪些文件属于分组"{group_name}"。考虑以下因素：
        1. 文件名中的关键词匹配
        2. 年份、季数、集数等信息
        3. 语言和格式标识
        4. 系列名称的相似性

        目标文件数量：约{target_count}个文件

        请返回JSON格式，包含匹配的文件索引：
        {{
            "matched_files": [0, 1, 2, ...],
            "reason": "匹配原因说明"
        }}

        只返回JSON，不要其他内容。
        """

        # 调用AI进行匹配
        response_content = call_ai_api(match_prompt, app_config.get('GROUPING_MODEL', ''))

        if response_content:
            result = parse_json_from_ai_response(response_content)
            if result:
                matched_indices = result.get('matched_files', [])
                reason = result.get('reason', '无说明')

                logging.info(f"🤖 AI匹配分组'{group_name}': {len(matched_indices)}个文件, 原因: {reason}")

                # 转换索引为文件ID
                matched_file_ids = []
                for idx in matched_indices:
                    if isinstance(idx, int) and 0 <= idx < len(available_files):
                        matched_file_ids.append(available_files[idx]['fileId'])

                return matched_file_ids

    except Exception as e:
        logging.error(f"AI文件匹配失败: {e}")

    return []



def get_filenames_by_ids(file_ids, video_files):
    """
    根据文件ID列表获取对应的文件名列表

    Args:
        file_ids (list): 文件ID列表
        video_files (list): 视频文件信息列表，每个元素包含fileId和filename字段

    Returns:
        list: 对应的文件名列表，保持与file_ids相同的顺序
    """
    file_names = []
    for file_id in file_ids:
        for video_file in video_files:
            if video_file['fileId'] == file_id:
                file_names.append(video_file['filename'])
                break
    return file_names

def validate_and_process_groups(movie_info_raw):
    """验证和处理分组信息"""
    if not movie_info_raw:
        return []

    # 处理可能的嵌套列表结构
    if isinstance(movie_info_raw, list):
        if len(movie_info_raw) > 0 and isinstance(movie_info_raw[0], list):
            # 如果是嵌套列表，取第一层
            movie_info = movie_info_raw[0]
        else:
            movie_info = movie_info_raw
    else:
        movie_info = [movie_info_raw] if movie_info_raw else []

    # 验证分组信息的有效性
    if movie_info and isinstance(movie_info, list) and len(movie_info) > 0:
        valid_groups = []
        for group in movie_info:
            if (isinstance(group, dict) and
                'group_name' in group and
                group['group_name'] and
                ('fileIds' in group or 'files' in group)):
                # 检查fileIds是否有效
                file_ids = group.get('fileIds', []) or group.get('files', [])
                if file_ids and isinstance(file_ids, list) and len(file_ids) > 0:
                    valid_groups.append(group)
        return valid_groups

    return []

def process_group_file_matching(valid_groups, video_files):
    """处理分组的文件匹配 - 优化版：直接返回原始分组结果，减少API调用"""
    if not valid_groups:
        return []

    # 🚀 优化：直接使用AI分组的原始结果，避免额外的API调用
    logging.info(f"⚡ 跳过批量文件匹配，直接使用原始分组结果: {len(valid_groups)} 个分组")
    logging.info(f"📊 可用视频文件数量: {len(video_files)} 个")



    # 直接返回原始分组结果，不进行额外的AI匹配
    return valid_groups

def enhance_groups_with_filenames(corrected_groups, video_files):
    """为分组添加文件名信息"""
    enhanced_groups = []
    for group in corrected_groups:
        enhanced_group = group.copy()
        file_ids = enhanced_group.get('fileIds', [])

        # 获取对应的文件名列表
        file_names = get_filenames_by_ids(file_ids, video_files)
        enhanced_group['file_names'] = file_names
        enhanced_groups.append(enhanced_group)

        # 调试日志
        logging.info(f"分组 '{enhanced_group['group_name']}': {len(file_ids)} 个文件ID, {len(file_names)} 个文件名")
        if len(file_names) > 0:
            logging.info(f"  文件名示例: {file_names[0] if file_names else '无'}")

    return enhanced_groups


# 这些全局变量已经移动到上面的全局变量声明区域

def load_application_config():
    """
    从配置文件加载应用程序配置

    如果配置文件不存在，则使用默认配置并创建配置文件。
    加载完成后更新所有相关的全局变量。

    Global Variables Updated:
        app_config: 主配置字典
        QPS_LIMIT, CHUNK_SIZE, MAX_WORKERS: 性能配置
        CLIENT_ID, CLIENT_SECRET: 123云盘API配置
        TMDB_API_KEY, GEMINI_API_KEY, GEMINI_API_URL: 第三方API配置
        MODEL, GROUPING_MODEL, LANGUAGE: AI和本地化配置
    """
    global app_config, QPS_LIMIT, CHUNK_SIZE, MAX_WORKERS, CLIENT_ID, CLIENT_SECRET
    global TMDB_API_KEY, AI_API_KEY, AI_API_URL, MODEL, GROUPING_MODEL, LANGUAGE
    global API_MAX_RETRIES, API_RETRY_DELAY, AI_API_TIMEOUT, AI_MAX_RETRIES, AI_RETRY_DELAY
    global TMDB_API_TIMEOUT, TMDB_MAX_RETRIES, TMDB_RETRY_DELAY, CLOUD_API_MAX_RETRIES, CLOUD_API_RETRY_DELAY
    global GROUPING_MAX_RETRIES, GROUPING_RETRY_DELAY, TASK_QUEUE_GET_TIMEOUT
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                app_config.update(loaded_config)
            logging.info(f"配置已从 {CONFIG_FILE} 加载。")
        except Exception as e:
            logging.error(f"加载配置文件 {CONFIG_FILE} 失败: {e}，将使用默认配置。")
    else:
        logging.info(f"配置文件 {CONFIG_FILE} 不存在，将创建并保存默认配置。")
        save_application_config()

    # 更新全局变量
    global ENABLE_QUALITY_ASSESSMENT, ENABLE_SCRAPING_QUALITY_ASSESSMENT

    QPS_LIMIT = app_config["QPS_LIMIT"]
    CHUNK_SIZE = app_config["CHUNK_SIZE"]
    MAX_WORKERS = app_config["MAX_WORKERS"]
    CLIENT_ID = app_config["CLIENT_ID"]
    CLIENT_SECRET = app_config["CLIENT_SECRET"]
    TMDB_API_KEY = app_config.get("TMDB_API_KEY", "")
    # 兼容旧配置：如果新配置不存在，使用旧配置
    AI_API_KEY = app_config.get("AI_API_KEY", "") or app_config.get("GEMINI_API_KEY", "")
    AI_API_URL = app_config.get("AI_API_URL", "") or app_config.get("GEMINI_API_URL", "")
    MODEL = app_config.get("MODEL", "gpt-3.5-turbo")
    GROUPING_MODEL = app_config.get("GROUPING_MODEL", "gpt-3.5-turbo")
    LANGUAGE = app_config.get("LANGUAGE", "zh-CN")

    # 更新重试和超时配置
    API_MAX_RETRIES = app_config.get("API_MAX_RETRIES", 3)
    API_RETRY_DELAY = app_config.get("API_RETRY_DELAY", 2)
    AI_API_TIMEOUT = app_config.get("AI_API_TIMEOUT", 60)
    AI_MAX_RETRIES = app_config.get("AI_MAX_RETRIES", 3)
    AI_RETRY_DELAY = app_config.get("AI_RETRY_DELAY", 2)
    TMDB_API_TIMEOUT = app_config.get("TMDB_API_TIMEOUT", 60)
    TMDB_MAX_RETRIES = app_config.get("TMDB_MAX_RETRIES", 3)
    TMDB_RETRY_DELAY = app_config.get("TMDB_RETRY_DELAY", 2)
    CLOUD_API_MAX_RETRIES = app_config.get("CLOUD_API_MAX_RETRIES", 3)
    CLOUD_API_RETRY_DELAY = app_config.get("CLOUD_API_RETRY_DELAY", 2)
    GROUPING_MAX_RETRIES = app_config.get("GROUPING_MAX_RETRIES", 3)
    GROUPING_RETRY_DELAY = app_config.get("GROUPING_RETRY_DELAY", 2)
    TASK_QUEUE_GET_TIMEOUT = app_config.get("TASK_QUEUE_GET_TIMEOUT", 1.0)
    ENABLE_QUALITY_ASSESSMENT = app_config.get("ENABLE_QUALITY_ASSESSMENT", False)
    ENABLE_SCRAPING_QUALITY_ASSESSMENT = app_config.get("ENABLE_SCRAPING_QUALITY_ASSESSMENT", True)
    logging.info(f"✅ 配置加载完成。QPS_LIMIT: {QPS_LIMIT}, CHUNK_SIZE: {CHUNK_SIZE}, MAX_WORKERS: {MAX_WORKERS}")
    logging.info(f"🔑 API配置状态 - CLIENT_ID: {'已设置' if CLIENT_ID else '未设置'}, CLIENT_SECRET: {'已设置' if CLIENT_SECRET else '未设置'}")
    logging.info(f"🎬 TMDB_API_KEY: {'已设置' if TMDB_API_KEY else '未设置'}, AI_API_KEY: {'已设置' if AI_API_KEY else '未设置'}")
    logging.info(f"🤖 AI模型配置 - MODEL: {MODEL}, GROUPING_MODEL: {GROUPING_MODEL}, LANGUAGE: {LANGUAGE}")
    logging.info(f"🌐 AI_API_URL: {'已设置' if AI_API_URL else '未设置'}")

def save_application_config():
    """
    将当前配置保存到配置文件

    Returns:
        bool: 保存成功返回True，失败返回False
    """
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_config, f, ensure_ascii=False, indent=4)
        logging.info(f"配置已保存到 {CONFIG_FILE}")
        return True
    except Exception as e:
        logging.error(f"保存配置文件 {CONFIG_FILE} 失败: {e}")
        return False

# ================================
# 自定义异常类
# ================================

class ClientCredentialsError(Exception):
    """123云盘客户端凭据错误异常"""
    def __init__(self, response_data):
        self.response_data = response_data
        super().__init__(f"错误的client_id或client_secret，请检查后重试\n{self.response_data}")


class AccessTokenError(Exception):
    """123云盘访问令牌错误异常"""
    def __init__(self, response_data):
        self.response_data = response_data
        super().__init__(f"错误的access_token，请检查后重试\n{self.response_data}")


class TokenLimitExceededError(Exception):
    """访问令牌使用次数超限异常"""
    def __init__(self, response_data):
        self.response_data = response_data
        super().__init__(f"访问令牌使用次数已超限，需要刷新令牌\n{self.response_data}")


class TaskCancelledException(Exception):
    """任务被取消异常"""
    pass


class APIRateLimitException(Exception):
    """API频率限制异常"""
    pass


class AccessTokenExpiredException(Exception):
    """访问令牌过期异常"""
    pass


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


class NetworkError(Exception):
    """网络错误异常"""
    pass


class FileSystemError(Exception):
    """文件系统错误异常"""
    pass


class ValidationError(Exception):
    """数据验证错误异常"""
    pass


class AIServiceError(Exception):
    """AI服务错误异常"""
    pass


class CacheError(Exception):
    """缓存操作错误异常"""
    pass


# ================================
# 配置管理类
# ================================

class ConfigManager:
    """
    统一的配置管理类

    Features:
    - 配置验证
    - 类型转换
    - 默认值处理
    - 配置更新通知
    """

    # 配置项定义和验证规则
    CONFIG_SCHEMA = {
        # 性能配置
        'QPS_LIMIT': {'type': int, 'min': 1, 'max': 50, 'default': 8},
        'CHUNK_SIZE': {'type': int, 'min': 10, 'max': 200, 'default': 50},
        'MAX_WORKERS': {'type': int, 'min': 1, 'max': 20, 'default': 6},

        # API配置
        'CLIENT_ID': {'type': str, 'required': False, 'default': ''},
        'CLIENT_SECRET': {'type': str, 'required': False, 'default': ''},
        'TMDB_API_KEY': {'type': str, 'required': False, 'default': ''},
        'AI_API_KEY': {'type': str, 'required': False, 'default': ''},
        'AI_API_URL': {'type': str, 'required': False, 'default': ''},

        # AI模型配置
        'MODEL': {'type': str, 'default': ''},
        'GROUPING_MODEL': {'type': str, 'default': ''},
        'LANGUAGE': {'type': str, 'default': 'zh-CN'},

        # 超时配置
        'AI_API_TIMEOUT': {'type': int, 'min': 5, 'max': 300, 'default': 30},
        'TMDB_API_TIMEOUT': {'type': int, 'min': 5, 'max': 60, 'default': 10},

        # 重试配置
        'AI_MAX_RETRIES': {'type': int, 'min': 1, 'max': 10, 'default': 3},
        'TMDB_MAX_RETRIES': {'type': int, 'min': 1, 'max': 10, 'default': 3},

        # 功能开关
        'KILL_OCCUPIED_PORT_PROCESS': {'type': bool, 'default': True},
        'ENABLE_QUALITY_ASSESSMENT': {'type': bool, 'default': False},
        'ENABLE_SCRAPING_QUALITY_ASSESSMENT': {'type': bool, 'default': True},
    }

    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = {}
        self.load_config()

    def validate_config_item(self, key, value):
        """验证单个配置项"""
        if key not in self.CONFIG_SCHEMA:
            raise ValidationError(f"未知的配置项: {key}")

        schema = self.CONFIG_SCHEMA[key]

        # 类型检查
        expected_type = schema['type']
        if not isinstance(value, expected_type):
            try:
                # 尝试类型转换
                if expected_type == int:
                    value = int(value)
                elif expected_type == float:
                    value = float(value)
                elif expected_type == bool:
                    if isinstance(value, str):
                        value = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        value = bool(value)
                elif expected_type == str:
                    value = str(value)
            except (ValueError, TypeError):
                raise ValidationError(f"配置项 {key} 类型错误，期望 {expected_type.__name__}，得到 {type(value).__name__}")

        # 范围检查
        if 'min' in schema and value < schema['min']:
            raise ValidationError(f"配置项 {key} 值 {value} 小于最小值 {schema['min']}")

        if 'max' in schema and value > schema['max']:
            raise ValidationError(f"配置项 {key} 值 {value} 大于最大值 {schema['max']}")

        # 必需项检查
        if schema.get('required', False) and not value:
            raise ValidationError(f"配置项 {key} 是必需的，不能为空")

        return value

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # 验证并应用配置
                for key, value in loaded_config.items():
                    if key in self.CONFIG_SCHEMA:
                        try:
                            validated_value = self.validate_config_item(key, value)
                            self.config[key] = validated_value
                        except ValidationError as e:
                            logging.warning(f"配置项 {key} 验证失败: {e}，使用默认值")
                            self.config[key] = self.CONFIG_SCHEMA[key]['default']
                    else:
                        # 保留未知配置项（向后兼容）
                        self.config[key] = value

                # 设置缺失配置项的默认值
                for key, schema in self.CONFIG_SCHEMA.items():
                    if key not in self.config:
                        self.config[key] = schema['default']

                logging.info(f"配置已从 {self.config_file} 加载并验证")
            else:
                # 使用默认配置
                for key, schema in self.CONFIG_SCHEMA.items():
                    self.config[key] = schema['default']

                logging.info(f"配置文件 {self.config_file} 不存在，使用默认配置")
                self.save_config()

        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise ConfigurationError(f"配置加载失败: {str(e)}")

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logging.info(f"配置已保存到 {self.config_file}")
            return True
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
            raise ConfigurationError(f"配置保存失败: {str(e)}")

    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key, value):
        """设置配置项"""
        validated_value = self.validate_config_item(key, value)
        self.config[key] = validated_value
        return validated_value

    def update(self, new_config):
        """批量更新配置"""
        validated_config = {}
        for key, value in new_config.items():
            if key in self.CONFIG_SCHEMA:
                validated_config[key] = self.validate_config_item(key, value)
            else:
                # 保留未知配置项
                validated_config[key] = value

        self.config.update(validated_config)
        return validated_config

    def get_all(self):
        """获取所有配置"""
        return self.config.copy()

    def get_stats(self):
        """获取配置统计信息"""
        return {
            'total_items': len(self.config),
            'schema_items': len(self.CONFIG_SCHEMA),
            'custom_items': len(self.config) - len(self.CONFIG_SCHEMA),
            'config_file': self.config_file
        }


# ================================
# 应用程序状态管理类
# ================================

class AppState:
    """
    应用程序状态管理类

    用于管理全局状态，减少全局变量的使用
    """

    def __init__(self):
        # 配置管理器
        self.config_manager = ConfigManager()

        # API相关状态
        self.access_token = None
        self.token_expiry = None

        # 任务管理状态
        self.current_task_id = None
        self.task_cancelled = False

        # QPS限制器
        self.qps_limiter = None

        # 日志队列
        self.log_queue = deque(maxlen=5000)

        # 初始化状态
        self._initialize_state()

    def _initialize_state(self):
        """初始化应用程序状态"""
        # QPS限制器将在后面初始化
        self.qps_limiter = None

        # 初始化访问令牌
        self.access_token = None  # 将在后面初始化

    def get_config(self, key, default=None):
        """获取配置项"""
        return self.config_manager.get(key, default)

    def set_config(self, key, value):
        """设置配置项"""
        return self.config_manager.set(key, value)

    def update_config(self, new_config):
        """批量更新配置"""
        return self.config_manager.update(new_config)

    def save_config(self):
        """保存配置"""
        return self.config_manager.save_config()

    def start_task(self, task_id):
        """开始新任务"""
        self.current_task_id = task_id
        self.task_cancelled = False
        logging.info(f"🚀 开始新任务: {task_id}")

    def cancel_task(self):
        """取消当前任务"""
        if self.current_task_id:
            self.task_cancelled = True
            logging.info(f"🛑 任务已取消: {self.current_task_id}")

    def check_task_cancelled(self):
        """检查任务是否被取消"""
        if self.task_cancelled:
            raise TaskCancelledException(f"任务已被用户取消: {self.current_task_id}")

    def add_log(self, message):
        """添加日志到队列"""
        self.log_queue.append({
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': message
        })

    def get_logs(self, limit=None):
        """获取日志"""
        if limit:
            return list(self.log_queue)[-limit:]
        return list(self.log_queue)

    def clear_logs(self):
        """清空日志"""
        self.log_queue.clear()

    def get_stats(self):
        """获取应用程序统计信息"""
        return {
            'current_task': self.current_task_id,
            'task_cancelled': self.task_cancelled,
            'log_count': len(self.log_queue),
            'config_stats': self.config_manager.get_stats(),
            'cache_stats': {
                'folder_path_cache': folder_path_cache.stats(),
                'grouping_cache': grouping_cache.stats(),
                'scraping_cache': scraping_cache.stats(),
                'folder_content_cache': folder_content_cache.stats()
            }
        }


# app_state将在QPSLimiter定义后创建


# ================================
# API装饰器
# ================================

def api_error_handler(func):
    """API错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TaskCancelledException:
            # 任务取消异常需要重新抛出
            raise
        except APIRateLimitException as e:
            logging.warning(f"⚠️ API频率限制: {e}")
            return jsonify({'success': False, 'error': 'API请求过于频繁，请稍后重试'})
        except AccessTokenExpiredException as e:
            logging.error(f"❌ 访问令牌过期: {e}")
            return jsonify({'success': False, 'error': '访问令牌已过期，请重新配置'})
        except ConfigurationError as e:
            logging.error(f"❌ 配置错误: {e}")
            return jsonify({'success': False, 'error': f'配置错误: {str(e)}'})
        except NetworkError as e:
            logging.error(f"❌ 网络错误: {e}")
            return jsonify({'success': False, 'error': f'网络连接失败: {str(e)}'})
        except ValidationError as e:
            logging.error(f"❌ 数据验证错误: {e}")
            return jsonify({'success': False, 'error': f'数据验证失败: {str(e)}'})
        except AIServiceError as e:
            logging.error(f"❌ AI服务错误: {e}")
            return jsonify({'success': False, 'error': f'AI服务不可用: {str(e)}'})
        except FileSystemError as e:
            logging.error(f"❌ 文件系统错误: {e}")
            return jsonify({'success': False, 'error': f'文件操作失败: {str(e)}'})
        except Exception as e:
            logging.error(f"❌ 未知错误: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'系统内部错误: {str(e)}'})

    return wrapper


# ================================
# 性能监控类
# ================================

class PerformanceMonitor:
    """
    性能监控类

    用于监控API调用性能、缓存命中率等关键指标
    """

    def __init__(self):
        self.metrics = {
            'api_calls': {},  # API调用统计
            'cache_hits': {},  # 缓存命中统计
            'response_times': {},  # 响应时间统计
            'error_counts': {},  # 错误计数
            'start_time': time.time()
        }
        self.lock = threading.Lock()

    def record_api_call(self, endpoint, duration, success=True):
        """记录API调用"""
        with self.lock:
            if endpoint not in self.metrics['api_calls']:
                self.metrics['api_calls'][endpoint] = {
                    'total_calls': 0,
                    'success_calls': 0,
                    'total_duration': 0,
                    'avg_duration': 0,
                    'min_duration': float('inf'),
                    'max_duration': 0
                }

            stats = self.metrics['api_calls'][endpoint]
            stats['total_calls'] += 1
            stats['total_duration'] += duration
            stats['avg_duration'] = stats['total_duration'] / stats['total_calls']
            stats['min_duration'] = min(stats['min_duration'], duration)
            stats['max_duration'] = max(stats['max_duration'], duration)

            if success:
                stats['success_calls'] += 1

    def record_cache_hit(self, cache_name, hit=True):
        """记录缓存命中"""
        with self.lock:
            if cache_name not in self.metrics['cache_hits']:
                self.metrics['cache_hits'][cache_name] = {
                    'hits': 0,
                    'misses': 0,
                    'hit_rate': 0
                }

            stats = self.metrics['cache_hits'][cache_name]
            if hit:
                stats['hits'] += 1
            else:
                stats['misses'] += 1

            total = stats['hits'] + stats['misses']
            stats['hit_rate'] = stats['hits'] / total if total > 0 else 0

    def record_error(self, error_type):
        """记录错误"""
        with self.lock:
            if error_type not in self.metrics['error_counts']:
                self.metrics['error_counts'][error_type] = 0
            self.metrics['error_counts'][error_type] += 1

    def get_stats(self):
        """获取性能统计"""
        with self.lock:
            uptime = time.time() - self.metrics['start_time']
            return {
                'uptime_seconds': uptime,
                'uptime_formatted': self._format_duration(uptime),
                'api_calls': self.metrics['api_calls'].copy(),
                'cache_hits': self.metrics['cache_hits'].copy(),
                'error_counts': self.metrics['error_counts'].copy()
            }

    def _format_duration(self, seconds):
        """格式化时间长度"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def reset_stats(self):
        """重置统计数据"""
        with self.lock:
            self.metrics = {
                'api_calls': {},
                'cache_hits': {},
                'response_times': {},
                'error_counts': {},
                'start_time': time.time()
            }


# 创建全局性能监控实例
performance_monitor = PerformanceMonitor()


def task_management_decorator(func):
    """任务管理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            # 开始新任务
            task_id = f"{func.__name__}_{int(time.time())}"
            start_new_task(task_id)

            # 清理操作相关缓存
            operation_type = getattr(func, '_operation_type', 'unknown')
            clear_operation_related_caches(operation_type=operation_type)

            # 执行函数
            result = func(*args, **kwargs)

            return result
        except TaskCancelledException:
            logging.info(f"🛑 任务 {func.__name__} 被用户取消")
            return jsonify({'success': False, 'error': '任务已被用户取消', 'cancelled': True})
        except Exception as e:
            logging.error(f"❌ 任务 {func.__name__} 执行失败: {e}", exc_info=True)
            raise

    return wrapper


def performance_monitor_decorator(endpoint_name=None):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                performance_monitor.record_error(type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                name = endpoint_name or func.__name__
                performance_monitor.record_api_call(name, duration, success)

        return wrapper
    return decorator


def validate_api_response(response):
    """
    验证123云盘API响应状态

    Args:
        response: requests.Response对象

    Returns:
        dict: API响应中的data部分

    Raises:
        TokenLimitExceededError: 当访问令牌使用次数超限时
        AccessTokenError: 当API返回其他认证错误时
        requests.HTTPError: 当HTTP状态码不是200时
    """
    if response.status_code == 200:
        response_data = json.loads(response.text)
        if response_data["code"] == 0:
            return response_data["data"]
        elif response_data["code"] == 401:
            # 检查是否是令牌使用次数超限
            message = response_data.get("message", "").lower()
            if "tokens number has exceeded" in message or "exceeded the limit" in message:
                raise TokenLimitExceededError(response_data)
            else:
                raise AccessTokenError(response_data)
        else:
            raise AccessTokenError(response_data)
    else:
        raise requests.HTTPError(response.text)

# 这些常量已经移动到上面的全局变量声明区域


# ================================
# 123云盘API核心函数
# ================================

# ================================
# 日志系统初始化
# ================================

class QueueHandler(logging.Handler):
    """自定义日志处理器，将日志消息添加到队列中供Web界面显示（Windows兼容性增强）"""
    def emit(self, record):
        try:
            log_entry = self.format(record)
            # 使用安全编码处理，避免Windows系统中的字符编码问题
            safe_log_entry = safe_log_message(log_entry)
            log_queue.append(safe_log_entry)
        except Exception as e:
            # 如果日志处理失败，添加一个错误消息而不是崩溃
            error_msg = f"[日志处理错误: {str(e)}]"
            log_queue.append(error_msg)


def initialize_logging_system():
    """
    初始化应用程序日志系统

    配置文件日志、控制台日志和Web界面日志队列
    """
    global root_logger, file_handler, console_handler, queue_handler

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除所有现有的处理器，避免重复日志
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加文件处理器（Windows兼容性：明确指定UTF-8编码）
    file_handler = RotatingFileHandler(
        'rename_log.log',
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding='utf-8'  # 明确指定UTF-8编码，解决Windows中文字符问题
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)

    # 添加控制台处理器（Windows兼容性：设置错误处理）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    # 在Windows系统中，控制台可能不支持某些Unicode字符，设置错误处理策略
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass  # 如果重配置失败，继续使用默认设置
    root_logger.addHandler(console_handler)

    # 添加自定义队列处理器
    queue_handler = QueueHandler()
    queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(queue_handler)

    # 确保 Flask 自己的日志也通过 root_logger 处理
    app.logger.addHandler(queue_handler)

    # 禁用 Werkzeug 的访问日志
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ================================
# QPS限制器类和初始化
# ================================

class QPSLimiter:
    """
    QPS（每秒查询数）限制器

    用于控制API请求频率，避免超过服务端限制
    """
    def __init__(self, qps_limit):
        self.qps_limit = float(qps_limit)
        self.interval = 1.0 / self.qps_limit
        self.last_request_time = 0
        self.lock = threading.Lock()

    def acquire(self):
        """获取请求许可，如果需要会阻塞等待"""
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.last_request_time
            if elapsed_time < self.interval:
                time.sleep(self.interval - elapsed_time)
            self.last_request_time = time.time()


# 创建全局应用程序状态实例（在QPSLimiter定义之后）
app_state = AppState()


def limit_path_depth(file_path, max_depth=3):
    """
    限制文件路径最多显示指定层数（从末尾开始计算）

    Args:
        file_path (str): 完整的文件路径
        max_depth (int): 最大显示层数，默认为3

    Returns:
        str: 限制层数后的路径
    """
    if not file_path:
        return file_path

    path_parts = file_path.split('/')
    if len(path_parts) > max_depth:
        return '/'.join(path_parts[-max_depth:])
    else:
        return file_path


def initialize_qps_limiters():
    """
    初始化各种API的QPS限制器

    基于123pan官方API限制创建专用限制器：
    - api/v2/file/list: 5 QPS
    - api/v1/file/move: 1 QPS
    - api/v1/file/delete: 1 QPS
    - api/v1/file/rename: 1 QPS
    """
    global qps_limiter, v2_list_limiter, rename_limiter, move_limiter, delete_limiter

    qps_limiter = QPSLimiter(qps_limit=QPS_LIMIT)  # 通用限制器，使用配置值
    v2_list_limiter = QPSLimiter(qps_limit=5)     # api/v2/file/list: 4 QPS (平衡性能和稳定性)
    rename_limiter = QPSLimiter(qps_limit=1)       # api/v1/file/rename: 保守使用1 QPS
    move_limiter = QPSLimiter(qps_limit=1)        # api/v1/file/move: 1 QPS (提高性能)
    delete_limiter = QPSLimiter(qps_limit=1)       # api/v1/file/delete: 1 QPS (提高性能)


def get_access_token_from_api(client_id: str, client_secret: str):
    """
    从123云盘API获取访问令牌

    Args:
        client_id (str): 123云盘开放平台客户端ID
        client_secret (str): 123云盘开放平台客户端密钥

    Returns:
        str or None: 访问令牌，失败时返回None
    """
    url = BASE_API_URL + "/api/v1/access_token"
    data = {"ClientID": client_id, "ClientSecret": client_secret}

    try:
        logging.info(f"🔑 尝试获取访问令牌，URL: {url}")
        logging.info(f"🔑 客户端ID: {client_id[:10]}...")
        # logging.info(f"🔑 请求数据: {data}")
        r = requests.post(url, json=data, headers=API_HEADERS)
        logging.info(f"🔑 HTTP状态码: {r.status_code}")
        # logging.info(f"🔑 响应内容: {r.text}")

        rdata = json.loads(r.text)
        if r.status_code == 200:
            if rdata["code"] == 0:
                logging.info("✅ 成功获取访问令牌")
                return rdata['data']['accessToken']
            else:
                logging.error(f"❌ API返回错误: {rdata}")
        else:
            logging.error(f"❌ HTTP请求失败: {r.status_code}")
    except Exception as e:
        logging.error(f"❌ 获取访问令牌时发生异常: {e}")

    return None


def initialize_access_token():
    """
    初始化123云盘访问令牌

    从本地文件读取或重新获取访问令牌，并更新全局请求头
    支持访问令牌过期检查和自动刷新

    Returns:
        str: 访问令牌
    """
    global access_token, access_token_expires_at
    token = ""

    if os.path.exists("123_access_token.txt"):
        # 如果存在访问令牌文件，读取并检查是否过期（Windows兼容性：指定UTF-8编码）
        with open("123_access_token.txt", "r", encoding='utf-8') as f:
            token = f.read().strip()
        logging.info("📁 从文件读取访问令牌")

        # 检查令牌是否过期
        if is_access_token_expired(token):
            logging.warning("⚠️ 本地访问令牌已过期，尝试获取新令牌")
            token = ""  # 清空过期的令牌
        else:
            logging.info("✅ 本地访问令牌仍然有效")

    # 如果没有有效令牌，尝试获取新令牌
    if not token and CLIENT_ID and CLIENT_SECRET:
        logging.info(f"🔑 CLIENT_ID: {'已设置' if CLIENT_ID else '未设置'}, CLIENT_SECRET: {'已设置' if CLIENT_SECRET else '未设置'}")
        token = get_access_token_from_api(CLIENT_ID, CLIENT_SECRET)
        if token:
            # 保存新令牌到文件（Windows兼容性：指定UTF-8编码）
            try:
                with open("123_access_token.txt", "w", encoding='utf-8') as f:
                    f.write(token)
                logging.info("✅ 成功获取并保存新访问令牌")
            except Exception as e:
                logging.error(f"❌ 保存访问令牌失败: {e}")
        else:
            logging.error("❌ 无法获取访问令牌，请检查CLIENT_ID和CLIENT_SECRET配置")
    elif not token:
        # 没有配置信息，应用程序仍然可以启动，但功能受限
        logging.warning("⚠️ 未配置CLIENT_ID和CLIENT_SECRET，请在网页配置页面设置")

    if token:
        # 更新全局变量
        access_token = token
        API_HEADERS["Authorization"] = f"Bearer {token}"
        logging.info("🔐 访问令牌已设置到请求头")

        # 解析并记录令牌过期时间
        payload = decode_jwt_token(token)
        if payload and payload.get('exp'):
            expires_at = datetime.datetime.fromtimestamp(payload['exp'])
            access_token_expires_at = expires_at
            logging.info(f"⏰ 访问令牌过期时间: {expires_at}")
        else:
            logging.warning("⚠️ 无法解析访问令牌过期时间")
    else:
        logging.warning("⚠️ 未设置访问令牌，123云盘功能将不可用")

    return token

def find_existing_folder(name: str, parent_id: int):
    """
    在指定父目录中查找同名文件夹

    Args:
        name (str): 文件夹名称
        parent_id (int): 父文件夹ID

    Returns:
        int or None: 如果找到返回文件夹ID，否则返回None
    """
    try:
        logging.info(f"🔍 在父目录 {parent_id} 中查找文件夹 '{name}'")
        folder_list = get_file_list_from_cloud(parent_id, 100)

        if 'fileList' in folder_list:
            for item in folder_list['fileList']:
                if item['type'] == 1 and item['filename'] == name:
                    logging.info(f"✅ 找到现有文件夹: {name}，文件夹ID: {item['fileId']}")
                    return item['fileId']

        # 如果在当前页没找到，进行分页查找
        last_file_id = folder_list.get('lastFileId', -1)
        while last_file_id != -1:
            try:
                next_page = get_file_list_from_cloud(parent_id, 100, last_file_id=last_file_id)
                if 'fileList' in next_page:
                    for item in next_page['fileList']:
                        if item['type'] == 1 and item['filename'] == name:
                            logging.info(f"✅ 在分页中找到现有文件夹: {name}，文件夹ID: {item['fileId']}")
                            return item['fileId']
                last_file_id = next_page.get('lastFileId', -1)
            except Exception as page_error:
                logging.error(f"分页查找时出错: {page_error}")
                break

        logging.info(f"📁 文件夹 '{name}' 在父目录 {parent_id} 中不存在")
        return None

    except Exception as e:
        logging.error(f"查找文件夹时出错: {e}")
        return None


@ensure_valid_access_token
def create_folder_in_cloud(name: str, parent_id: int):
    """
    在123云盘中创建文件夹，如果文件夹已存在则返回现有文件夹ID

    Args:
        name (str): 文件夹名称
        parent_id (int): 父文件夹ID，根目录为0

    Returns:
        dict: API响应数据，包含文件夹ID

    API返回数据格式:
        {
            "data": {
                "dirID": number  # 文件夹ID（新建或现有）
            }
        }
    """
    # 首先检查文件夹是否已存在
    existing_folder_id = find_existing_folder(name, parent_id)
    if existing_folder_id:
        logging.info(f"📁 文件夹 '{name}' 已存在，直接使用现有文件夹ID: {existing_folder_id}")
        return {'data': {'dirID': existing_folder_id}}

    # 文件夹不存在，创建新文件夹
    logging.info(f"📁 准备创建新文件夹: {name}，父目录ID: {parent_id}")
    url = BASE_API_URL + "/upload/v1/file/mkdir"
    data = {"name": name, "parentID": parent_id}

    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            logging.info(f"创建文件夹请求 (尝试 {attempt + 1}/{max_retries}): {data}")
            # 使用POST方法和JSON格式发送请求
            r = requests.post(url, json=data, headers=API_HEADERS)
            logging.info(f"HTTP响应状态码: {r.status_code}")
            logging.info(f"HTTP响应内容: {r.text}")

            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            result = validate_api_response(r)
            logging.info(f"✅ 文件夹创建成功: {name}，新文件夹ID: {result.get('dirID')}")
            return {'data': result}
        except (AccessTokenError, TokenLimitExceededError) as e:
            logging.error(f"访问令牌错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            # 检查是否是文件夹已存在的错误（可能在检查和创建之间有其他进程创建了同名文件夹）
            if isinstance(e, AccessTokenError):
                error_data = e.args[0] if e.args else {}
                if isinstance(error_data, dict) and error_data.get('message') == '该目录下已经有同名文件夹,无法进行创建':
                    logging.info(f"📁 文件夹 '{name}' 在创建过程中被其他进程创建，重新查找")
                    existing_folder_id = find_existing_folder(name, parent_id)
                    if existing_folder_id:
                        return {'data': {'dirID': existing_folder_id}}
                    else:
                        logging.error(f"❌ 文件夹 '{name}' 创建失败且无法找到现有文件夹")
                        raise e

            # 其他访问令牌错误，继续重试逻辑
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.error(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise  # Re-raise the last exception if all retries fail


@ensure_valid_access_token
def get_file_list_from_cloud(parent_file_id: int, limit: int, search_data=None, search_mode=None, last_file_id=None):
    """
    从123云盘获取文件列表（分页）

    Args:
        parent_file_id (int): 父文件夹ID，根目录为0
        limit (int): 每页返回的文件数量限制
        search_data (str, optional): 搜索关键词
        search_mode (str, optional): 搜索模式
        last_file_id (int, optional): 上一页最后一个文件的ID，用于分页

    Returns:
        dict: API响应数据，包含文件列表和分页信息
    """
    v2_list_limiter.acquire()  # 使用专用的v2_list限流器（15 QPS）
    # current_time = datetime.datetime.now()
    # formatted_time = current_time.strftime("%H:%M:%S")
    # print("v2_list:",formatted_time)
    url = BASE_API_URL + "/api/v2/file/list"
    data = {"parentFileId": parent_file_id, "limit": limit}
    if search_data:
        data["searchData"] = search_data
    if search_mode:
        data["searchMode"] = search_mode
    if last_file_id:
        data["lastFileID"] = last_file_id

    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            r = requests.get(url, data=data, headers=API_HEADERS)
            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            result = validate_api_response(r)

            # 获取当前文件夹的路径前缀
            current_path_prefix = get_folder_full_path(parent_file_id)

            # 为每个文件和文件夹添加 file_name 字段（完整路径，限制最多倒数三层）
            if "fileList" in result:
                for item in result["fileList"]:
                    full_path = os.path.join(current_path_prefix, item['filename']) if current_path_prefix else item['filename']
                    # 限制路径最多显示倒数三层
                    item['file_name'] = limit_path_depth(full_path, 3)

            return result
        except requests.exceptions.RequestException as e:
            print(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise  # Re-raise the last exception if all retries fail


def get_all_files_in_folder(folder_id, limit=100, check_cancellation=False):
    """
    获取指定文件夹下的所有文件（自动处理分页）

    Args:
        folder_id (int): 文件夹ID
        limit (int): 每页返回的文件数量限制，默认100
        check_cancellation (bool): 是否检查任务取消状态，默认False

    Returns:
        list: 包含所有文件信息的列表
    """
    # 只在明确要求时检查任务是否被取消
    if check_cancellation:
        check_task_cancelled()

    try:
        filelist = get_file_list_from_cloud(folder_id, limit=limit)
        all_files = filelist["fileList"]
        last_file_id = filelist["lastFileId"]

        while last_file_id != -1:
            # 只在明确要求时检查任务是否被取消
            if check_cancellation:
                check_task_cancelled()

            # QPS控制已经在QPSLimiter中实现，无需额外延迟

            next_page = get_file_list_from_cloud(folder_id, last_file_id=last_file_id, limit=limit)
            all_files.extend(next_page["fileList"])
            last_file_id = next_page["lastFileId"]

        return all_files
    except Exception as e:
        # 如果是429错误或API频率限制，返回空列表而不是抛出异常
        if "429" in str(e) or "操作频繁" in str(e):
            logging.warning(f"⚠️ API频率限制，跳过文件夹 {folder_id}: {e}")
            return []
        else:
            # 其他错误继续抛出
            raise


def get_folder_full_path(folder_id):
    """
    获取文件夹的完整路径（带缓存优化）

    Args:
        folder_id (int): 文件夹ID，根目录为0

    Returns:
        str: 文件夹的完整路径，根目录返回空字符串
    """
    global folder_path_cache

    if folder_id == 0:
        return ""

    # 检查缓存
    if folder_id in folder_path_cache:
        return folder_path_cache[folder_id]

    paths = []
    fid = folder_id
    uncached_folders = []

    # 收集未缓存的文件夹ID
    while fid != 0 and fid not in folder_path_cache:
        uncached_folders.append(fid)
        try:
            folder_details = detail(fid)
            paths.append(folder_details['filename'])
            fid = int(folder_details["parentFileID"])
        except Exception as e:
            logging.warning(f"获取文件夹 {fid} 路径失败: {e}")
            break

    # 如果找到了缓存的父路径，使用它
    if fid != 0 and fid in folder_path_cache:
        parent_path = folder_path_cache[fid]
        if parent_path:
            paths.append(parent_path)

    paths.reverse()
    full_path = "/".join(paths)

    # 缓存所有路径（包括中间路径）
    current_path = ""
    for i, folder_id_to_cache in enumerate(reversed(uncached_folders)):
        if i == 0:
            current_path = paths[0] if paths else ""
        else:
            current_path = "/".join(paths[:i+1]) if len(paths) > i else current_path
        folder_path_cache[folder_id_to_cache] = current_path

    return full_path


def get_video_files_for_naming(folder_id, file_list, max_files=200, max_depth=3):
    """
    为智能重命名功能优化的视频文件获取函数

    Args:
        folder_id (int): 要搜索的文件夹ID
        file_list (list): 用于存储找到的视频文件的列表（会被修改）
        max_files (int): 最大文件数量限制，默认200
        max_depth (int): 最大扫描深度，默认3层

    Note:
        此函数专门为智能重命名功能优化，限制扫描深度和文件数量以提高性能
    """
    logging.info(f"🎯 开始智能重命名文件扫描 - 最大文件数: {max_files}, 最大深度: {max_depth}")

    def _scan_folder_limited(folder_id, current_path="", depth=0):
        # 检查任务是否被取消
        check_task_cancelled()

        # 检查深度限制
        if depth >= max_depth:
            logging.info(f"⏹️ 达到最大扫描深度 {max_depth}，停止扫描: {current_path}")
            return

        # 检查文件数量限制
        if len(file_list) >= max_files:
            logging.info(f"⏹️ 达到最大文件数量 {max_files}，停止扫描")
            return

        if not current_path:
            current_path = get_folder_full_path(folder_id)
            logging.info(f"🔍 智能重命名扫描 - 根路径: {current_path}")

        try:
            # 获取文件夹内容
            all_files = get_all_files_in_folder(folder_id, limit=100, check_cancellation=True)
            logging.info(f"📂 智能重命名扫描 {folder_id} ({current_path}) - {len(all_files)} 个项目 (深度: {depth})")

            # 分离视频文件和子文件夹
            video_files_in_folder = []
            subfolders = []

            for file_item in all_files:
                if len(file_list) >= max_files:
                    break

                if file_item['type'] == 0:  # 文件
                    _, ext = os.path.splitext(file_item['filename'])
                    if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                        video_files_in_folder.append(file_item)
                elif file_item['type'] == 1:  # 文件夹
                    subfolders.append(file_item)

            # 处理当前文件夹中的视频文件
            if video_files_in_folder:
                gb_in_bytes = 1024 ** 3
                for file_item in video_files_in_folder:
                    if len(file_list) >= max_files:
                        break

                    bytes_value = file_item['size']
                    gb_value = bytes_value / gb_in_bytes
                    full_file_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']
                    file_path = limit_path_depth(full_file_path, 3)

                    enhanced_file_item = file_item.copy()
                    enhanced_file_item['file_path'] = file_path
                    enhanced_file_item['size_gb'] = f"{gb_value:.1f}GB"

                    file_list.append(enhanced_file_item)

                logging.info(f"✅ 发现 {len(video_files_in_folder)} 个视频文件: {current_path}")

            # 递归处理子文件夹（如果还没达到限制）
            if depth < max_depth - 1 and len(file_list) < max_files and subfolders:
                # 限制子文件夹数量，优先处理可能包含更多内容的文件夹
                limited_subfolders = subfolders[:20]  # 最多处理20个子文件夹

                for subfolder in limited_subfolders:
                    if len(file_list) >= max_files:
                        break

                    subfolder_path = os.path.join(current_path, subfolder['filename']) if current_path else subfolder['filename']
                    _scan_folder_limited(subfolder['fileId'], subfolder_path, depth + 1)

                if len(subfolders) > 20:
                    logging.info(f"⚠️ 子文件夹数量 ({len(subfolders)}) 超过限制，只处理前20个")

        except Exception as e:
            logging.error(f"智能重命名扫描文件夹 {folder_id} 时发生错误: {e}")

    # 开始扫描
    _scan_folder_limited(folder_id)

    logging.info(f"🎯 智能重命名文件扫描完成 - 共找到 {len(file_list)} 个视频文件")


def get_video_files_recursively(folder_id, file_list, current_path="", depth=0, use_concurrent=True):
    """
    递归获取指定文件夹及其子文件夹中的所有视频文件（优化版本）

    Args:
        folder_id (int): 要搜索的文件夹ID
        file_list (list): 用于存储找到的视频文件的列表（会被修改）
        current_path (str): 当前文件夹的路径，用于构建完整文件路径
        depth (int): 递归深度，用于控制日志输出
        use_concurrent (bool): 是否使用并发优化，默认True

    Note:
        此函数会修改传入的file_list参数，将找到的视频文件添加到其中
    """
    # 检查任务是否被取消
    check_task_cancelled()

    if not current_path:
        current_path = get_folder_full_path(folder_id)
        logging.info(f"🔍 调试 - 使用get_folder_full_path获取路径: {current_path}")
    else:
        logging.info(f"🔍 调试 - 使用传递的路径: {current_path}")

    try:
        # 使用最大允许的limit值（100），如果有更多文件会自动分页处理
        # 在AI分析任务中启用取消检查
        all_files = get_all_files_in_folder(folder_id, limit=100, check_cancellation=True)

        # 输出扫描进度日志
        if depth == 0:  # 根级别总是输出
            logging.info(f"📂 扫描文件夹 {folder_id} ({current_path}) - {len(all_files)} 个项目")
        elif len(all_files) > 50:  # 大文件夹输出进度
            logging.info(f"📂 扫描子文件夹 {folder_id} ({current_path}) - {len(all_files)} 个项目")
        elif depth % 3 == 0:  # 每3层输出一次进度
            logging.info(f"📂 扫描文件夹 {folder_id} ({current_path}) - {len(all_files)} 个项目")

        # 批量处理视频文件（优化性能）
        video_files_in_folder = []
        subfolders = []

        for file_item in all_files:
            if file_item['type'] == 0:  # 文件
                _, ext = os.path.splitext(file_item['filename'])
                if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                    video_files_in_folder.append(file_item)
            elif file_item['type'] == 1:  # 文件夹
                subfolders.append(file_item)

        # 批量处理视频文件
        if video_files_in_folder:
            gb_in_bytes = 1024 ** 3
            for file_item in video_files_in_folder:
                bytes_value = file_item['size']
                gb_value = bytes_value / gb_in_bytes
                # 构建完整的文件路径
                full_file_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']

                # 限制路径最多显示倒数三层
                file_path = limit_path_depth(full_file_path, 3)

                # 创建增强的文件项，保留原有信息并添加计算字段
                enhanced_file_item = file_item.copy()
                enhanced_file_item['file_path'] = file_path
                enhanced_file_item['size_gb'] = f"{gb_value:.1f}GB"

                file_list.append(enhanced_file_item)

            # 输出视频文件发现日志
            if depth == 0:  # 根目录总是输出
                logging.info(f"✅ 发现 {len(video_files_in_folder)} 个视频文件: {current_path}")
            elif len(video_files_in_folder) > 5:  # 有较多视频文件时输出
                logging.info(f"✅ 发现 {len(video_files_in_folder)} 个视频文件: {current_path}")
            elif len(video_files_in_folder) > 0 and depth <= 2:  # 浅层目录有视频文件时输出
                logging.info(f"✅ 发现 {len(video_files_in_folder)} 个视频文件: {current_path}")

        # 处理子文件夹 - 根据情况选择串行或并发
        if subfolders:
            if subfolders and (depth == 0 or len(subfolders) > 5):
                logging.info(f"🔄 开始处理 {len(subfolders)} 个子文件夹: {current_path}")

            # 决定是否使用并发处理（重新启用，使用保守设置）
            should_use_concurrent = (
                use_concurrent and
                depth == 0 and  # 只在根级别使用并发
                len(subfolders) >= 20 and  # 20个文件夹以上启用并发
                len(subfolders) <= 200  # 200个文件夹以下使用并发
            )

            # 调试日志
            
            logging.info(f"🔍 并发条件检查: use_concurrent={use_concurrent}, depth={depth}, subfolders={len(subfolders)}, should_use_concurrent={should_use_concurrent}")

            if should_use_concurrent:
                logging.info(f"🚀 启用并发处理模式")
                _process_subfolders_concurrent(subfolders, file_list, current_path, depth)
            else:
                logging.info(f"📝 使用串行处理模式（避免API频率限制）")
                _process_subfolders_sequential(subfolders, file_list, current_path, depth)

        # 输出完成统计（根目录或大文件夹）
        if depth == 0:
            total_videos = len([f for f in file_list if f.get('file_path', '').startswith(current_path or '')])
            logging.info(f"🏁 文件夹扫描完成: {current_path} - 共发现 {total_videos} 个视频文件")
        elif len(subfolders) > 10:
            logging.info(f"✅ 子文件夹处理完成: {current_path} - {len(subfolders)} 个子文件夹")

    except Exception as e:
        if "任务已被用户取消" in str(e):
            raise  # 重新抛出取消异常
        logging.error(f"处理文件夹 {folder_id} ({current_path}) 时发生错误: {e}", exc_info=True)

def _process_subfolders_sequential(subfolders, file_list, current_path, depth):
    """串行处理子文件夹"""
    for i, file_item in enumerate(subfolders):
        try:
            # 在处理每个子文件夹前检查任务是否被取消
            check_task_cancelled()

            # 输出处理进度（大文件夹或根目录）
            if depth == 0 and len(subfolders) > 10 and (i + 1) % 5 == 0:
                logging.info(f"📁 处理进度: {i + 1}/{len(subfolders)} 个子文件夹")

            # 添加额外延迟以进一步减少API调用频率
            import time
            time.sleep(0.05)  # 50ms额外延迟

            # 构建子文件夹的路径（避免重复API调用）
            subfolder_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']
            # 缓存子文件夹路径
            folder_path_cache[file_item['fileId']] = subfolder_path
            # 递归处理子文件夹
            get_video_files_recursively(file_item['fileId'], file_list, subfolder_path, depth + 1, use_concurrent=False)
        except Exception as e:
            if "任务已被用户取消" in str(e):
                raise  # 重新抛出取消异常
            # 如果是429错误，记录但继续处理其他文件夹
            if "429" in str(e) or "操作频繁" in str(e):
                logging.warning(f"⚠️ API频率限制，跳过文件夹: {file_item['filename']}")
                continue
            logging.error(f"处理子文件夹 {file_item['filename']} 时发生错误: {e}")
            continue  # 继续处理其他文件夹

def _process_subfolders_concurrent(subfolders, file_list, current_path, depth):
    """并发处理子文件夹（仅用于根级别的大文件夹）"""
    logging.info(f"🚀 使用并发模式处理 {len(subfolders)} 个子文件夹")

    # 预先缓存所有子文件夹路径（使用简单路径构建，避免API调用）
    for file_item in subfolders:
        subfolder_path = os.path.join(current_path, file_item['filename']) if current_path else file_item['filename']
        folder_path_cache[file_item['fileId']] = subfolder_path

    # 使用适度的并发线程数以平衡性能和稳定性
    max_workers = min(5, len(subfolders))  # 提高到5个线程
    completed_count = 0

    def process_single_subfolder(file_item):
        qps_limiter.acquire()
        """处理单个子文件夹的函数"""
        try:
            check_task_cancelled()
            subfolder_path = folder_path_cache[file_item['fileId']]
            subfolder_files = []

            # QPS控制已经在QPSLimiter中实现，无需额外延迟

            get_video_files_recursively(file_item['fileId'], subfolder_files, subfolder_path, depth + 1, use_concurrent=False)
            return subfolder_files
        except Exception as e:
            if "任务已被用户取消" in str(e):
                raise
            # 如果是429错误，记录但不中断整个处理
            if "429" in str(e) or "操作频繁" in str(e):
                logging.warning(f"⚠️ API频率限制: {file_item['filename']} - 跳过此文件夹")
                return []
            logging.error(f"并发处理子文件夹 {file_item['fileId']} 失败: {e}")
            return []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 分批提交任务以减少并发压力
        batch_size = 5
        for i in range(0, len(subfolders), batch_size):
            batch = subfolders[i:i + batch_size]
            future_to_folder = {executor.submit(process_single_subfolder, folder): folder for folder in batch}

            # 收集当前批次的结果
            for future in as_completed(future_to_folder):
                folder_item = future_to_folder[future]
                try:
                    subfolder_files = future.result()
                    file_list.extend(subfolder_files)
                    completed_count += 1

                    # 输出进度
                    if completed_count % 5 == 0 or completed_count == len(subfolders):
                        logging.info(f"📁 并发处理进度: {completed_count}/{len(subfolders)} 个子文件夹完成")

                except Exception as e:
                    if "任务已被用户取消" in str(e):
                        logging.info("🛑 并发处理被用户取消")
                        raise
                    logging.error(f"处理子文件夹 {folder_item['filename']} 时发生错误: {e}")

            # QPS控制已经在QPSLimiter中实现，无需批次间延迟


@ensure_valid_access_token
def rename(rename_dict: dict, use_batch_qps=False):
    """
    重命名文件
    :param rename_dict: 重命名字典 {file_id: new_name}
    :param use_batch_qps: 是否使用批量重命名的QPS限制（1 QPS）
    """

    rename_limiter.acquire()
    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime("%H:%M:%S")
    print("rename:",formatted_time)
    logging.info(f"开始重命名操作，重命名字典: {rename_dict}，使用批量QPS: {use_batch_qps}")

    url = BASE_API_URL + "/api/v1/file/rename"
    rename_list = []
    for i in rename_dict.keys():
        rename_list.append(f"{i}|{rename_dict[i]}")
    data = {"renameList": rename_list}

    logging.info(f"重命名API URL: {url}")
    logging.info(f"重命名数据: {data}")
    logging.info(f"请求头: {API_HEADERS}")

    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            logging.info(f"发送重命名请求 (尝试 {attempt + 1}/{max_retries})")
            # 使用JSON格式发送请求，符合API要求
            r = requests.post(url, json=data, headers=API_HEADERS)
            logging.info(f"HTTP响应状态码: {r.status_code}")
            logging.info(f"HTTP响应内容: {r.text}")

            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            result = validate_api_response(r)
            logging.info(f"重命名API返回结果: {result}")
            return result
        except (AccessTokenError, TokenLimitExceededError) as e:
            logging.error(f"访问令牌错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise
        except requests.exceptions.RequestException as e:
            logging.error(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise  # Re-raise the last exception if all retries fail


@ensure_valid_access_token
def detail(file_id):
    # 使用通用QPS限制器控制detail API调用频率
    qps_limiter.acquire()

    # 添加额外延迟以进一步减少API调用频率
    import time
    time.sleep(0.1)  # 100ms额外延迟

    # current_time = datetime.datetime.now()
    # formatted_time = current_time.strftime("%H:%M:%S")
    # print("detail:",formatted_time)
    url = BASE_API_URL + "/api/v1/file/detail"
    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            data = {"fileID": file_id}
            r = requests.get(url, data=data, headers=API_HEADERS)
            data = validate_api_response(r)
            if data["trashed"] == 1:
                data["trashed"] = True
            else:
                data["trashed"] = False
            if data["type"] == 1:
                data["type"] = "folder"
            else:
                data["type"] = "file"
            return data
        except requests.exceptions.RequestException as e:
            print(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                raise  # Re-raise the last exception if all retries fail


def trash(file_id_list: list):
    delete_limiter.acquire()
    # current_time = datetime.datetime.now()
    # formatted_time = current_time.strftime("%H:%M:%S")
    # print("delete:",formatted_time)
    url = BASE_API_URL + "/api/v1/file/trash"
    data = {"fileIDs": file_id_list}
    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            # 使用JSON格式发送请求，符合API要求
            r = requests.post(url, json=data, headers=API_HEADERS)
            logging.info(f"deleteAPI HTTP响应状态码: {r.status_code}")
            logging.info(f"deleteAPI HTTP响应内容: {r.text}")
            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # 检查API响应
            response_data = json.loads(r.text)
            if response_data.get("code") == 0:
                logging.info(f"delete操作成功: {response_data}")
                return {"success": True, "message": "delete成功"}
            else:
                error_message = response_data.get("message", "未知错误")
                logging.error(f"delete操作失败: {response_data}")
                return {"success": False, "message": error_message, "response": response_data}

        except requests.exceptions.RequestException as e:
            logging.error(f"delete请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                return {"success": False, "message": f"请求失败: {str(e)}"}


def delete(file_id_list: list):
    delete_limiter.acquire()
    # current_time = datetime.datetime.now()
    # formatted_time = current_time.strftime("%H:%M:%S")
    # print("delete:",formatted_time)

    url = BASE_API_URL + "/api/v1/file/delete"
    data = {"fileIDs": file_id_list}
    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            trash(file_id_list)
            r = requests.post(url, json=data, headers=API_HEADERS)
            logging.info(f"deleteAPI HTTP响应状态码: {r.status_code}")
            logging.info(f"deleteAPI HTTP响应内容: {r.text}")
            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # 检查API响应
            response_data = json.loads(r.text)
            if response_data.get("code") == 0:
                logging.info(f"delete操作成功: {response_data}")
                return {"success": True, "message": "delete成功"}
            else:
                error_message = response_data.get("message", "未知错误")
                logging.error(f"delete操作失败: {response_data}")
                return {"success": False, "message": error_message, "response": response_data}
        except requests.exceptions.RequestException as e:
            logging.error(f"delete请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                return {"success": False, "message": f"请求失败: {str(e)}"}


@ensure_valid_access_token
def move(file_id_list: list, to_parent_file_id: int):
    move_limiter.acquire()  # 使用专用的move限流器（10 QPS）
    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime("%H:%M:%S")
    print("move:",formatted_time)
    url = BASE_API_URL + "/api/v1/file/move"
    data = {"fileIDs": file_id_list,"toParentFileID": to_parent_file_id}
    max_retries = CLOUD_API_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            # 使用JSON格式发送请求，符合API要求
            r = requests.post(url, json=data, headers=API_HEADERS)
            logging.info(f"移动API HTTP响应状态码: {r.status_code}")
            logging.info(f"移动API HTTP响应内容: {r.text}")
            r.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # 检查API响应
            response_data = json.loads(r.text)
            if response_data.get("code") == 0:
                logging.info(f"移动操作成功: {response_data}")
                return {"success": True, "message": "移动成功"}
            else:
                error_message = response_data.get("message", "未知错误")
                logging.error(f"移动操作失败: {response_data}")
                return {"success": False, "message": error_message, "response": response_data}

        except requests.exceptions.RequestException as e:
            logging.error(f"移动请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(CLOUD_API_RETRY_DELAY)
            else:
                return {"success": False, "message": f"请求失败: {str(e)}"}



def sanitize_filename(filename):
    """
    清理文件名，确保Windows和其他系统兼容性

    Args:
        filename (str): 原始文件名

    Returns:
        str: 清理后的文件名
    """
    # 移除或替换不允许的字符
    # Windows文件名不允许的字符: < > : " / \ | ? *
    # Linux/macOS文件名不允许的字符: /
    # 这里我们处理所有常见的不允许字符
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Windows保留名称检查（CON, PRN, AUX, NUL, COM1-9, LPT1-9）
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }

    name_without_ext = os.path.splitext(sanitized)[0].upper()
    if name_without_ext in reserved_names:
        sanitized = f"_{sanitized}"  # 添加前缀避免保留名称冲突

    # 移除文件名开头和结尾的空格和点（Windows不允许）
    sanitized = sanitized.strip(' .')

    # 确保文件名不为空
    if not sanitized:
        sanitized = "unnamed_file"

    # 确保文件名长度不超过255个字符（常见文件系统限制）
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:(255 - len(ext))] + ext

    return sanitized


def safe_encode_for_windows(text):
    """
    安全编码文本以避免Windows系统中的字符编码问题

    Args:
        text (str): 需要编码的文本

    Returns:
        str: 安全编码后的文本
    """
    if not isinstance(text, str):
        text = str(text)

    try:
        # 尝试编码为UTF-8并解码，确保字符串是有效的UTF-8
        text.encode('utf-8').decode('utf-8')
        return text
    except UnicodeEncodeError:
        # 如果编码失败，使用错误处理策略
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except UnicodeDecodeError:
        # 如果解码失败，使用错误处理策略
        return text.encode('utf-8', errors='ignore').decode('utf-8')


def safe_log_message(message):
    """
    安全处理日志消息，避免Windows系统中的编码错误

    Args:
        message (str): 日志消息

    Returns:
        str: 安全处理后的日志消息
    """
    try:
        # 确保消息是字符串类型
        if not isinstance(message, str):
            message = str(message)

        # 使用安全编码处理
        safe_message = safe_encode_for_windows(message)

        # 替换可能导致问题的特殊字符
        # 某些控制字符在Windows控制台中可能导致显示问题
        safe_message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '?', safe_message)

        return safe_message
    except Exception:
        # 如果所有处理都失败，返回一个安全的默认消息
        return "[日志消息编码错误]"



# 智能文件分组辅助函数
def group_files_by_folder(files):
    """按文件夹路径分组文件"""
    folder_groups = {}
    for video_file in files:
        file_path = video_file.get('file_path', video_file['filename'])
        # 提取子文件夹路径（去掉文件名）
        folder_path = os.path.dirname(file_path)
        if folder_path not in folder_groups:
            folder_groups[folder_path] = []
        folder_groups[folder_path].append(video_file)
    return folder_groups

def split_files_into_batches(files, batch_size):
    """将文件列表拆分为批次"""
    return [files[i:i + batch_size] for i in range(0, len(files), batch_size)]



def merge_duplicate_named_groups(groups):
    """合并具有相同名称的分组（解决批处理导致的重复分组问题）"""
    if not groups or len(groups) < 2:
        return groups

    logging.info(f"🔄 开始合并重复命名的分组: {len(groups)} 个分组")

    # 按分组名称分类
    groups_by_name = {}
    for group in groups:
        group_name = group.get('group_name', '')
        if not group_name:
            continue

        if group_name not in groups_by_name:
            groups_by_name[group_name] = []
        groups_by_name[group_name].append(group)

    # 合并同名分组
    merged_groups = []
    for group_name, same_name_groups in groups_by_name.items():
        if len(same_name_groups) == 1:
            # 只有一个分组，直接添加
            merged_groups.append(same_name_groups[0])
        else:
            # 有多个同名分组，需要合并
            logging.info(f"🔗 合并重复分组 '{group_name}': {len(same_name_groups)} 个分组")

            # 合并所有文件ID和文件名
            all_file_ids = []
            all_file_names = []
            all_files = []
            folder_paths = set()

            for group in same_name_groups:
                file_ids = group.get('fileIds', [])
                file_names = group.get('file_names', [])
                files = group.get('files', [])
                folder_path = group.get('folder_path', '')

                all_file_ids.extend(file_ids)
                all_file_names.extend(file_names)
                all_files.extend(files)

                if folder_path:
                    folder_paths.add(folder_path)

            # 去重（保持顺序）
            seen_ids = set()
            unique_file_ids = []
            for file_id in all_file_ids:
                if file_id not in seen_ids:
                    unique_file_ids.append(file_id)
                    seen_ids.add(file_id)

            seen_names = set()
            unique_file_names = []
            for file_name in all_file_names:
                if file_name not in seen_names:
                    unique_file_names.append(file_name)
                    seen_names.add(file_name)

            seen_files = set()
            unique_files = []
            for file_item in all_files:
                file_key = str(file_item)  # 简单的去重方式
                if file_key not in seen_files:
                    unique_files.append(file_item)
                    seen_files.add(file_key)

            # 创建合并后的分组
            merged_group = {
                'group_name': group_name,
                'fileIds': unique_file_ids,
                'file_names': unique_file_names,
                'files': unique_files,
                'folder_path': '; '.join(folder_paths) if len(folder_paths) > 1 else list(folder_paths)[0] if folder_paths else '',
                'file_count': len(unique_file_ids)
            }

            merged_groups.append(merged_group)
            logging.info(f"✅ 合并完成 '{group_name}': {len(unique_file_ids)} 个文件")

    logging.info(f"🎯 重复分组合并完成: {len(groups)} → {len(merged_groups)} 个分组")
    return merged_groups

def merge_same_series_groups(groups):
    """使用AI智能合并同一系列的分组，支持分批处理"""
    if not groups or len(groups) < 2:
        return groups

    logging.info(f"🔄 开始AI智能合并分组: 输入 {len(groups)} 个分组")

    # 如果分组数量太多，先使用传统方法预处理
    if len(groups) > 20:
        logging.info(f"⚠️ 分组数量过多 ({len(groups)} 个)，先使用传统方法预处理")
        groups = merge_same_series_groups_traditional(groups)
        if len(groups) < 2:
            return groups

    # 准备分组信息供AI分析
    group_info = []
    for i, group in enumerate(groups):
        group_name = group.get('group_name', f'分组{i+1}')
        file_count = len(group.get('fileIds', []))
        file_names = group.get('file_names', [])

        # 取前5个文件名作为示例，提供更多信息帮助AI判断
        sample_files = file_names[:5] if file_names else []

        # 分析内容类型
        content_type = "unknown"
        movie_indicators = ["剧场版", "电影", "Movie", "代号：白", "Code:", "剧场", "大电影"]
        tv_indicators = ["第", "季", "集", "S0", "E0", "Season", "Episode", "EP"]

        # 检查是否为电影/剧场版
        if any(indicator in name for indicator in movie_indicators for name in sample_files):
            content_type = "movie"
        # 检查是否为电视剧集
        elif any(indicator in name for indicator in tv_indicators for name in sample_files):
            content_type = "tv_series"
        # 根据分组名称判断
        elif any(indicator in group_name for indicator in movie_indicators):
            content_type = "movie"
        elif any(indicator in group_name for indicator in tv_indicators):
            content_type = "tv_series"
        elif len(sample_files) > 0:
            # 根据文件名模式判断
            first_file = sample_files[0]
            if "(" in first_file and ")" in first_file and len(sample_files) < 5:
                # 包含年份且文件数量少的通常是电影
                content_type = "movie"
            elif len(sample_files) > 10:
                # 文件数量多的通常是电视剧集
                content_type = "tv_series"

        group_info.append({
            'name': group_name,
            'file_count': file_count,
            'sample_files': sample_files,
            'content_type': content_type,
            'series_indicators': {
                'has_sequels': any(str(i) in name for i in range(2, 10) for name in sample_files),
                'has_seasons': any("季" in name or "Season" in name for name in sample_files),
                'has_episodes': any("集" in name or "Episode" in name for name in sample_files)
            }
        })

    # 构建AI分析的输入
    analysis_input = f"""请分析以下分组列表，判断哪些分组应该合并：

重要提醒：
- 绝对不要将电影和电视剧集合并（即使是同一IP）
- 绝对不要将剧场版电影和电视动画合并
- 绝对不要将不同的动漫/电影系列合并
- **🚫 绝对禁止将不同季的电视剧合并！每季必须保持独立！**
- 只有真正属于同一系列且内容类型相同的才能合并

**🚫 严格禁止的合并行为：**
- ❌ 老友记 S01 + 老友记 S02 → 老友记 S01-S02 (绝对禁止！)
- ❌ 权力的游戏 S01 + 权力的游戏 S02 → 权力的游戏 S01-S02 (绝对禁止！)
- ❌ 任何 "S01-S10" 这样的跨季合并格式 (绝对禁止！)

**✅ 正确的处理方式：**
- ✅ 老友记 S01 保持独立
- ✅ 老友记 S02 保持独立
- ✅ 每个季度都是独立的分组

特别注意：
- "代号：白"、"剧场版"等是电影，不能与电视剧集合并
- "S01"、"Season"等是电视剧集，不能与电影合并
- 同一IP的电影和电视剧应该分开管理

分组列表: {json.dumps(group_info, ensure_ascii=False, indent=2)}

请严格按照规则分析，如果不确定是否应该合并，请选择不合并。"""

    try:
        # 调用AI进行分组合并分析
        merge_result = extract_movie_info_from_filename_enhanced(analysis_input, GROUP_MERGE_PROMPT, GROUPING_MODEL)

        if not merge_result or not isinstance(merge_result, dict):
            logging.warning("AI分组合并分析失败，使用传统方法")
            return merge_same_series_groups_traditional(groups)

        merges = merge_result.get('merges', [])
        if not merges:
            logging.info("🤖 AI判断无需合并分组")
            return groups

        # 执行AI建议的合并
        merged_groups = []
        processed_groups = set()

        for merge in merges:
            merged_name = merge.get('merged_name', '')
            groups_to_merge = merge.get('groups_to_merge', [])
            reason = merge.get('reason', '')

            if len(groups_to_merge) < 2:
                continue

            # 🚫 代码级别检查：阻止不同季的合并
            if 'S' in merged_name and '-S' in merged_name:
                logging.warning(f"🚫 阻止跨季合并: {merged_name} - 不同季不能合并！")
                continue

            # 检查是否包含不同季的分组
            season_numbers = set()
            for group_name in groups_to_merge:
                import re
                season_match = re.search(r'S(\d+)', group_name)
                if season_match:
                    season_numbers.add(season_match.group(1))

            if len(season_numbers) > 1:
                logging.warning(f"🚫 阻止跨季合并: {groups_to_merge} - 包含不同季 {season_numbers}！")
                continue

            logging.info(f"🤖 AI建议合并: {groups_to_merge} -> {merged_name} (理由: {reason})")

            # 找到要合并的分组
            target_groups = []
            for group in groups:
                if group.get('group_name') in groups_to_merge:
                    target_groups.append(group)
                    processed_groups.add(group.get('group_name'))

            if len(target_groups) >= 2:
                # 执行合并
                merged_group = merge_groups(target_groups, merged_name)
                merged_groups.append(merged_group)
                logging.info(f"✅ 成功合并: {merged_name} ({len(merged_group.get('fileIds', []))} 个文件)")

        # 添加未被合并的分组
        for group in groups:
            if group.get('group_name') not in processed_groups:
                merged_groups.append(group)

        logging.info(f"🎯 AI智能合并完成: {len(groups)} -> {len(merged_groups)} 个分组")
        return merged_groups

    except Exception as e:
        logging.error(f"AI分组合并出错: {e}，使用传统方法")
        return merge_same_series_groups_traditional(groups)


def merge_same_series_groups_traditional(groups):
    """传统的基于字符串匹配的分组合并方法"""
    if not groups:
        return groups

    logging.info(f"🔄 开始传统方法合并分组: 输入 {len(groups)} 个分组")

    # 按系列名称分组
    series_groups = {}
    for group in groups:
        group_name = group.get('group_name', '')
        if not group_name:
            continue

        # 提取系列基础名称（去掉数字、年份等）
        base_series_name = extract_series_base_name(group_name)

        if base_series_name not in series_groups:
            series_groups[base_series_name] = []
        series_groups[base_series_name].append(group)

    # 合并同一系列的分组
    merged_groups = []
    for base_name, group_list in series_groups.items():
        if len(group_list) == 1:
            # 只有一个分组，直接保留
            merged_groups.append(group_list[0])
        else:
            # 多个分组，需要合并
            logging.info(f"🔗 传统方法合并系列 '{base_name}': {len(group_list)} 个分组")
            merged_group = merge_groups(group_list, f"{base_name}系列")
            merged_groups.append(merged_group)

    logging.info(f"🎯 传统方法合并完成: 输出 {len(merged_groups)} 个分组")
    return merged_groups


def merge_groups(group_list, merged_name):
    """合并多个分组为一个分组"""
    # 合并所有文件ID和文件名
    merged_file_ids = []
    merged_file_names = []
    folder_paths = []

    for group in group_list:
        merged_file_ids.extend(group.get('fileIds', []))
        merged_file_names.extend(group.get('file_names', []))
        folder_path = group.get('folder_path', '')
        if folder_path and folder_path not in folder_paths:
            folder_paths.append(folder_path)

    # 去重文件ID（防止重复）
    unique_file_ids = list(dict.fromkeys(merged_file_ids))
    unique_file_names = list(dict.fromkeys(merged_file_names))

    # 创建合并后的分组
    merged_group = {
        'group_name': merged_name,
        'fileIds': unique_file_ids,
        'file_names': unique_file_names,
        'folder_path': ' + '.join(folder_paths) if folder_paths else '',
        'merged_from': [g.get('group_name', '') for g in group_list]
    }

    return merged_group

def extract_series_base_name(group_name):
    """
    提取系列的基础名称，用于识别同一系列的不同分组

    Args:
        group_name (str): 分组名称

    Returns:
        str: 提取的基础系列名称

    Examples:
        "宝可梦系列" -> "宝可梦"
        "海贼王电影系列" -> "海贼王"
        "龙珠Z合集" -> "龙珠"
    """
    # 移除常见的系列后缀
    series_suffixes = [
        '系列', '合集', '全集', '电影系列', '剧场版系列', '特别篇',
        'Series', 'Collection', 'Complete', 'Movies', 'Films'
    ]
    base_name = group_name.strip()

    # 按长度排序，优先匹配较长的后缀
    series_suffixes.sort(key=len, reverse=True)

    for suffix in series_suffixes:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)].strip()
            break  # 只移除第一个匹配的后缀

    # 移除常见的系列标识符和数字
    # 保留核心名称，例如: "龙珠Z" -> "龙珠", "海贼王" -> "海贼王"
    base_name = re.sub(r'\s*第[0-9]+[部季期]\s*', '', base_name)  # 移除"第X部/季/期"
    base_name = re.sub(r'\s*[0-9]+\s*', '', base_name)          # 移除独立数字
    base_name = re.sub(r'\s*[Z]\s*', '', base_name)             # 移除常见的系列标识符Z
    base_name = base_name.strip()

    # 如果处理后为空，返回原始名称
    if not base_name:
        base_name = group_name.strip()

    logging.debug(f"系列名称提取: '{group_name}' -> '{base_name}'")
    return base_name

def process_files_for_grouping(files, source_name):
    """处理文件进行智能分组 - 优化版"""
    if not files:
        return []

    logging.info(f"🔄 处理 '{source_name}': {len(files)} 个文件")

    try:
        check_task_cancelled()
    except:
        pass

    # 批次处理逻辑 - 优化API调用次数
    MAX_BATCH_SIZE = CHUNK_SIZE  # 增加批处理大小，减少API调用次数
    if len(files) > MAX_BATCH_SIZE:
        return _process_files_in_batches(files, MAX_BATCH_SIZE)
    else:
        return _process_single_batch(files)


def _process_files_in_batches(files, batch_size):
    """分批处理文件"""
    batches = split_files_into_batches(files, batch_size)
    logging.info(f"📦 分批处理: {len(batches)} 批")

    all_groups = []
    for i, batch_files in enumerate(batches):
        try:
            check_task_cancelled()
        except:
            pass

        logging.info(f"📦 处理第 {i+1}/{len(batches)} 批: {len(batch_files)} 个文件")
        batch_groups = _call_ai_for_grouping(batch_files)

        if batch_groups:
            all_groups.extend(batch_groups if isinstance(batch_groups, list) else [batch_groups])

        logging.info(f"✅ 第 {i+1} 批完成: {len(batch_groups) if batch_groups else 0} 个分组")

    return all_groups


def _process_single_batch(files):
    """处理单批文件"""
    logging.info(f"📊 单批处理 {len(files)} 个文件")
    return _call_ai_for_grouping(files)


def _call_ai_for_grouping(files):
    """调用AI进行分组并验证结果"""
    file_list = [{'fileId': f['fileId'], 'filename': f['filename']} for f in files]
    user_input = repr(file_list)

    logging.info(f"🤖 开始AI分组分析: {len(files)} 个文件")
    start_time = time.time()

    try:
        raw_result = extract_movie_info_from_filename_enhanced(user_input, MAGIC_PROMPT, GROUPING_MODEL)
        process_time = time.time() - start_time

        if raw_result:
            logging.info(f"⏱️ AI分组耗时: {process_time:.2f}秒 - 成功")
            # 验证和增强分组结果
            return _validate_and_enhance_groups(raw_result, files, "AI分组")
        else:
            logging.warning(f"⏱️ AI分组耗时: {process_time:.2f}秒 - 无结果")
            return []
    except Exception as e:
        process_time = time.time() - start_time
        logging.error(f"❌ AI分组失败: {process_time:.2f}秒 - {e}")
        return []


# 处理AI返回的分组结果 - 移到独立函数
def _validate_and_enhance_groups(raw_groups, files, source_name):
    """验证和增强AI分组结果"""
    movie_info = []
    if raw_groups:
        if isinstance(raw_groups, list):
            if len(raw_groups) > 0 and isinstance(raw_groups[0], list):
                movie_info = raw_groups[0]
            else:
                movie_info = raw_groups
        else:
            movie_info = [raw_groups] if raw_groups else []

    # 验证和增强分组信息
    enhanced_groups = []
    if movie_info and isinstance(movie_info, list):
        logging.info(f"📋 开始验证 {len(movie_info)} 个分组")
        for i, group in enumerate(movie_info):
            if isinstance(group, dict) and 'group_name' in group:
                enhanced_group = group.copy()
                group_name = group.get('group_name', '')
                ai_file_ids = group.get('fileIds', []) or group.get('files', [])

                # 验证分组
                if len(ai_file_ids) < 2:
                    logging.info(f"⏭️ 跳过单文件分组 '{group_name}': 只有 {len(ai_file_ids)} 个文件")
                    continue

                if len(ai_file_ids) > 50:
                    logging.warning(f"🚫 拒绝超大分组 '{group_name}': 包含 {len(ai_file_ids)} 个文件")
                    continue

                # 验证文件名相关性
                file_names_for_validation = []
                for file_id in ai_file_ids:
                    for video_file in files:
                        if video_file['fileId'] == file_id:
                            file_names_for_validation.append(video_file['filename'])
                            break

                if len(file_names_for_validation) >= 2:
                    # 检查文件名相关性
                    first_file = file_names_for_validation[0]
                    base_name = first_file.split('(')[0].strip() if '(' in first_file else first_file.split('.')[0].strip()

                    related_count = 0
                    for file_name in file_names_for_validation:
                        if base_name in file_name or any(str(i) in file_name for i in range(1, 10)):
                            related_count += 1

                    if related_count < len(file_names_for_validation) * 0.5:
                        logging.warning(f"🚫 拒绝可疑分组 '{group_name}': 文件名相关性不足 ({related_count}/{len(file_names_for_validation)})")
                        continue

                # 获取完整的文件名列表
                file_names = []
                logging.info(f"🔍 开始匹配文件名: ai_file_ids={ai_file_ids[:3]}...")
                logging.info(f"🔍 可用文件数量: {len(files)}, 示例文件ID: {[f.get('fileId', 'N/A') for f in files[:3]]}")

                for file_id in ai_file_ids:
                    found = False
                    for video_file in files:
                        if str(video_file['fileId']) == str(file_id):  # 确保类型匹配
                            file_names.append(video_file['filename'])
                            found = True
                            break
                    if not found:
                        logging.warning(f"⚠️ 未找到文件ID {file_id} 对应的文件名")

                logging.info(f"🔍 匹配结果: 找到 {len(file_names)} 个文件名: {file_names[:3]}...")

                # 构建增强的分组信息，确保数据格式兼容性
                enhanced_group['fileIds'] = ai_file_ids
                enhanced_group['file_names'] = file_names
                enhanced_group['folder_path'] = source_name
                enhanced_group['group_name'] = group_name
                enhanced_group['files'] = file_names     # 前端需要文件名列表
                enhanced_groups.append(enhanced_group)

                logging.info(f"✅ 成功保留分组 '{group_name}': {len(ai_file_ids)} 个文件")
                logging.info(f"📝 分组数据: fileIds={ai_file_ids[:3]}..., file_names={file_names[:3]}...")
            else:
                logging.warning(f"⏭️ 跳过无效分组 (第 {i+1} 个): 缺少必要字段")

    # 确保最终结果的数据格式一致性
    for group in enhanced_groups:
        if 'file_names' in group and 'files' not in group:
            group['files'] = group['file_names']

    logging.info(f"🎯 验证完成: 生成 {len(enhanced_groups)} 个有效分组")

    # 调试：输出最终分组数据结构
    for i, group in enumerate(enhanced_groups[:2]):  # 只输出前2个分组的详细信息
        logging.info(f"🔍 分组 {i+1} 数据结构: {list(group.keys())}")
        if 'files' in group:
            logging.info(f"🔍 分组 {i+1} files字段: {group['files'][:3] if len(group['files']) > 3 else group['files']}")
        if 'file_names' in group:
            logging.info(f"🔍 分组 {i+1} file_names字段: {group['file_names'][:3] if len(group['file_names']) > 3 else group['file_names']}")

    return enhanced_groups

# ================================
# 质量评估和智能重试机制
# ================================

def log_extraction_summary(movie_info_list, user_input_content):
    """
    记录电影信息提取的详细总结
    """
    if not movie_info_list:
        logging.error("📋 提取总结: 未能提取到任何有效信息")
        return

    file_count = len(user_input_content.split('\n')) if user_input_content else 0
    extracted_count = len(movie_info_list) if isinstance(movie_info_list, list) else 0

    logging.info(f"📋 提取总结: {extracted_count}/{file_count} 个文件成功提取信息")

    if isinstance(movie_info_list, list):
        # 统计媒体类型分布
        media_types = {}
        years = []

        for item in movie_info_list:
            if isinstance(item, dict):
                media_type = item.get('media_type', 'unknown')
                media_types[media_type] = media_types.get(media_type, 0) + 1

                year = item.get('year')
                if year:
                    try:
                        years.append(int(year))
                    except (ValueError, TypeError):
                        pass

        # 记录媒体类型分布
        if media_types:
            type_summary = ', '.join([f"{k}: {v}" for k, v in media_types.items()])
            logging.info(f"📊 媒体类型分布: {type_summary}")

        # 记录年份范围
        if years:
            min_year, max_year = min(years), max(years)
            logging.info(f"📅 年份范围: {min_year} - {max_year}")


def log_tmdb_search_summary(results):
    """
    记录TMDB搜索结果的详细总结
    """
    if not results:
        return

    total = len(results)
    success = len([r for r in results if r.get('status') == 'success'])
    no_match = len([r for r in results if r.get('status') == 'no_match'])
    errors = len([r for r in results if r.get('status') == 'error'])

    logging.info(f"🎯 TMDB搜索总结: 成功={success}, 无匹配={no_match}, 错误={errors}, 总计={total}")

    # 统计匹配质量分布
    quality_scores = []
    for result in results:
        if result.get('match_quality') and 'score' in result['match_quality']:
            quality_scores.append(result['match_quality']['score'])

    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        high_quality = len([s for s in quality_scores if s >= 80])
        logging.info(f"📊 匹配质量: 平均分={avg_quality:.1f}, 高质量匹配={high_quality}/{len(quality_scores)}")


def handle_extraction_error(error, attempt, max_attempts, strategy_name=""):
    """
    统一的提取错误处理函数
    """
    error_msg = str(error)

    # 根据错误类型提供不同的处理建议
    if "timeout" in error_msg.lower():
        suggestion = "建议检查网络连接或增加超时时间"
    elif "json" in error_msg.lower():
        suggestion = "AI响应格式异常，可能需要调整提示词"
    elif "api" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
        suggestion = "API认证失败，请检查API密钥配置"
    elif "429" in error_msg:
        suggestion = "API请求频率过高，建议降低QPS设置"
    else:
        suggestion = "未知错误，建议检查日志详情"

    is_warning = attempt < max_attempts
    prefix = f"⚠️ {strategy_name}" if strategy_name else "❌"

    if is_warning:
        logging.warning(f"{prefix} 尝试 {attempt}/{max_attempts} 失败: {error_msg}")
        logging.warning(f"💡 处理建议: {suggestion}")
    else:
        logging.error(f"{prefix} 尝试 {attempt}/{max_attempts} 失败: {error_msg}")
        logging.error(f"💡 处理建议: {suggestion}")

    return suggestion

def validate_grouping_result(groups_data, file_list):
    """
    验证分组结果，过滤掉明显错误的分组

    Args:
        groups_data: 分组数据，格式为 [{"group_name": "...", "fileIds": [...]}]
        file_list: 原始文件列表，包含文件名信息

    Returns:
        list: 验证后的分组数据
    """
    if not groups_data or not isinstance(groups_data, list):
        return []

    validated_groups = []

    for group in groups_data:
        if not isinstance(group, dict) or 'group_name' not in group or 'fileIds' not in group:
            continue

        file_ids = group['fileIds']
        if len(file_ids) < 2:  # 单个文件不分组
            continue

        # 获取这个分组中的文件名
        group_filenames = []
        for file_id in file_ids:
            for file_info in file_list:
                if file_info.get('id') == file_id:
                    group_filenames.append(file_info.get('name', ''))
                    break

        # 验证分组的合理性
        if validate_group_similarity(group_filenames):
            validated_groups.append(group)
        else:
            logging.warning(f"🚫 过滤掉不合理的分组: {group['group_name']} - 文件: {group_filenames}")

    return validated_groups

def validate_group_similarity(filenames):
    """
    验证一组文件名是否真的属于同一系列

    Args:
        filenames: 文件名列表

    Returns:
        bool: 是否为合理的分组
    """
    if len(filenames) < 2:
        return False

    # 提取主要关键词
    keywords_sets = []
    for filename in filenames:
        # 移除年份、分辨率、编码等信息，提取核心关键词
        clean_name = re.sub(r'\(\d{4}\)', '', filename)  # 移除年份
        clean_name = re.sub(r'\{[^}]*\}', '', clean_name)  # 移除{}内容
        clean_name = re.sub(r'\[[^\]]*\]', '', clean_name)  # 移除[]内容
        clean_name = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv|webm)$', '', clean_name, flags=re.IGNORECASE)  # 移除扩展名

        # 分割成关键词
        keywords = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', clean_name))
        keywords = {kw for kw in keywords if len(kw) > 1}  # 过滤单字符
        keywords_sets.append(keywords)

    # 检查是否有共同的核心关键词
    if not keywords_sets:
        return False

    # 计算交集
    common_keywords = keywords_sets[0]
    for keywords in keywords_sets[1:]:
        common_keywords = common_keywords.intersection(keywords)

    # 如果有足够的共同关键词，认为是合理分组
    return len(common_keywords) >= 1 and any(len(kw) >= 2 for kw in common_keywords)

def evaluate_grouping_quality(grouping_result):
    """
    评估智能分组结果的质量

    Args:
        grouping_result: AI返回的分组结果

    Returns:
        dict: 包含质量分数和详细评估结果
    """
    if not grouping_result:
        return {"score": 0, "issues": ["无效的分组结果"], "valid_count": 0, "total_count": 0, "valid_ratio": 0}

    # 如果是单个分组对象，转换为列表
    if isinstance(grouping_result, dict):
        grouping_result = [grouping_result]

    if not isinstance(grouping_result, list):
        return {"score": 0, "issues": ["分组结果格式错误"], "valid_count": 0, "total_count": 0, "valid_ratio": 0}

    total_score = 0
    total_items = len(grouping_result)
    valid_count = 0
    issues = []

    for i, group in enumerate(grouping_result):
        item_score = 0
        item_issues = []

        if not isinstance(group, dict):
            item_issues.append("分组项不是字典格式")
            continue

        # 检查必需字段
        if 'group_name' in group and group['group_name']:
            group_name = str(group['group_name']).strip()
            if len(group_name) >= 2:
                item_score += 40  # 分组名称占40%权重
            else:
                item_issues.append(f"分组名称过短: {group_name}")
        else:
            item_issues.append("缺少分组名称")

        if 'fileIds' in group and group['fileIds']:
            file_ids = group['fileIds']
            if isinstance(file_ids, list) and len(file_ids) >= 2:
                item_score += 60  # 文件ID列表占60%权重
                # 额外检查：文件数量合理性
                if len(file_ids) <= 50:  # 合理的分组大小
                    item_score = min(100, item_score + 10)
            else:
                item_issues.append(f"文件ID列表无效或少于2个文件: {file_ids}")
        else:
            item_issues.append("缺少文件ID列表")

        if item_score >= 70:  # 认为是有效分组
            valid_count += 1

        total_score += item_score
        if item_issues:
            issues.extend([f"分组 {i+1}: {issue}" for issue in item_issues])

    average_score = total_score / total_items if total_items > 0 else 0

    return {
        "score": round(average_score, 2),
        "issues": issues,
        "valid_count": valid_count,
        "total_count": total_items,
        "valid_ratio": round(valid_count / total_items * 100, 2) if total_items > 0 else 0
    }


def evaluate_extraction_quality(movie_info_list):
    """
    评估电影信息提取结果的质量

    Args:
        movie_info_list: AI提取的电影信息列表

    Returns:
        dict: 包含质量分数和详细评估结果
    """
    if not movie_info_list or not isinstance(movie_info_list, list):
        return {"score": 0, "issues": ["无效的提取结果"], "valid_count": 0}

    total_score = 0
    total_items = len(movie_info_list)
    valid_count = 0
    issues = []

    for i, item in enumerate(movie_info_list):
        if not isinstance(item, dict):
            issues.append(f"项目 {i+1}: 不是有效的字典格式")
            continue

        item_score = 0
        item_issues = []

        # 检查必需字段
        required_fields = ['original_title', 'title', 'year', 'media_type']
        for field in required_fields:
            if field in item and item[field]:
                if field == 'year':
                    # 验证年份格式和合理性
                    try:
                        year = int(str(item[field]))
                        if 1900 <= year <= 2030:
                            item_score += 25  # 年份占25%权重
                        else:
                            item_issues.append(f"年份不合理: {year}")
                    except (ValueError, TypeError):
                        item_issues.append(f"年份格式错误: {item[field]}")
                elif field == 'media_type':
                    # 验证媒体类型
                    if item[field].lower() in ['movie', 'tv', 'tv_series', 'anime']:
                        item_score += 15  # 媒体类型占15%权重
                    else:
                        item_issues.append(f"未知媒体类型: {item[field]}")
                elif field in ['original_title', 'title']:
                    # 验证标题长度和内容
                    title = str(item[field]).strip()
                    if len(title) >= 2 and not title.isdigit():
                        item_score += 30  # 每个标题占30%权重
                    else:
                        item_issues.append(f"{field}过短或无效: {title}")
            else:
                item_issues.append(f"缺少必需字段: {field}")

        # 额外质量检查
        if item_score >= 80:  # 基础分数达标
            # 检查标题一致性
            if 'original_title' in item and 'title' in item:
                orig_title = str(item['original_title']).strip().lower()
                title = str(item['title']).strip().lower()
                if orig_title and title and (orig_title == title or orig_title in title or title in orig_title):
                    item_score = min(100, item_score + 10)  # 标题一致性加分

        if item_score >= 70:  # 认为是有效项目
            valid_count += 1

        total_score += item_score
        if item_issues:
            issues.extend([f"项目 {i+1}: {issue}" for issue in item_issues])

    average_score = total_score / total_items if total_items > 0 else 0

    return {
        "score": round(average_score, 2),
        "issues": issues,
        "valid_count": valid_count,
        "total_count": total_items,
        "valid_ratio": round(valid_count / total_items * 100, 2) if total_items > 0 else 0
    }


def evaluate_tmdb_match_quality(movie_info, tmdb_result):
    """
    评估TMDB搜索结果的匹配质量

    Args:
        movie_info: 提取的电影信息
        tmdb_result: TMDB搜索结果

    Returns:
        dict: 包含匹配质量分数和详细信息
    """
    if not tmdb_result or not movie_info:
        return {"score": 0, "reasons": ["无搜索结果或输入信息"]}

    score = 0
    reasons = []

    try:
        # 年份匹配检查 (40%权重) - 更严格的年份匹配
        movie_year = str(movie_info.get('year', ''))
        tmdb_date = tmdb_result.get('release_date') or tmdb_result.get('first_air_date', '')
        if tmdb_date and movie_year:
            tmdb_year = tmdb_date[:4]
            year_diff = abs(int(tmdb_year) - int(movie_year))
            if year_diff == 0:
                score += 40
                reasons.append(f"年份完全匹配: {movie_year}")
            elif year_diff <= 1:
                score += 30
                reasons.append(f"年份接近匹配: {movie_year} vs {tmdb_year}")
            elif year_diff <= 3:
                score += 15  # 降低模糊匹配分数
                reasons.append(f"年份模糊匹配: {movie_year} vs {tmdb_year}")
            elif year_diff <= 10:
                score -= 10  # 年份差异较大时扣分
                reasons.append(f"年份差异较大: {movie_year} vs {tmdb_year} (扣分)")
            else:
                score -= 30  # 年份差异过大时严重扣分
                reasons.append(f"年份差异过大: {movie_year} vs {tmdb_year} (严重扣分)")

        # 标题相似度检查 (40%权重)
        movie_title = str(movie_info.get('title', '')).lower().strip()
        tmdb_title = str(tmdb_result.get('title') or tmdb_result.get('name', '')).lower().strip()

        if movie_title and tmdb_title:
            if movie_title == tmdb_title:
                score += 40
                reasons.append("标题完全匹配")
            elif movie_title in tmdb_title or tmdb_title in movie_title:
                score += 30
                reasons.append("标题部分匹配")
            else:
                # 检查关键词匹配
                movie_words = set(movie_title.split())
                tmdb_words = set(tmdb_title.split())
                common_words = movie_words.intersection(tmdb_words)
                if len(common_words) >= 2:
                    score += 20
                    reasons.append(f"标题关键词匹配: {common_words}")
                elif len(common_words) >= 1:
                    score += 10
                    reasons.append(f"标题部分关键词匹配: {common_words}")
                else:
                    reasons.append("标题无明显匹配")

        # 媒体类型匹配检查 (20%权重)
        movie_type = str(movie_info.get('media_type', '')).lower()
        is_movie_result = 'release_date' in tmdb_result
        is_tv_result = 'first_air_date' in tmdb_result

        if movie_type == 'movie' and is_movie_result:
            score += 20
            reasons.append("媒体类型匹配: 电影")
        elif movie_type in ['tv', 'tv_series'] and is_tv_result:
            score += 20
            reasons.append("媒体类型匹配: 电视剧")
        elif movie_type and (is_movie_result or is_tv_result):
            score += 10
            reasons.append("媒体类型部分匹配")

        # TMDB ID直接匹配 (额外加分)
        if movie_info.get('tmdb_id') and str(movie_info['tmdb_id']) == str(tmdb_result.get('id', '')):
            score += 20
            reasons.append("TMDB ID直接匹配")

    except Exception as e:
        reasons.append(f"评估过程出错: {str(e)}")

    return {
        "score": min(100, score),  # 最高100分
        "reasons": reasons
    }


def extract_movie_info_from_filename_enhanced(user_input_content, EXTRACTION_PROMPT, model=None, max_attempts=3, enable_quality_assessment=None):
    """
    增强版电影信息提取函数，支持多次尝试和质量评估

    Args:
        user_input_content: 输入的文件名内容
        EXTRACTION_PROMPT: 提取提示词
        model: 使用的AI模型
        max_attempts: 最大尝试次数
        enable_quality_assessment: 是否启用质量评估，None时根据提示词类型自动判断

    Returns:
        最佳质量的提取结果
    """
    logging.info(f"🎯 开始增强版电影信息提取，最大尝试次数: {max_attempts}")

    # 如果没有指定模型，使用默认的MODEL；如果是MAGIC_PROMPT，使用GROUPING_MODEL
    model = MODEL

    # 判断是否为分组提示词
    is_grouping_prompt = "分组" in EXTRACTION_PROMPT or "group_name" in EXTRACTION_PROMPT or "fileIds" in EXTRACTION_PROMPT

    # 根据参数和提示词类型决定是否启用质量评估
    if enable_quality_assessment is None:
        # 自动判断：分组使用ENABLE_QUALITY_ASSESSMENT，刮削使用ENABLE_SCRAPING_QUALITY_ASSESSMENT
        use_quality_assessment = ENABLE_QUALITY_ASSESSMENT if is_grouping_prompt else ENABLE_SCRAPING_QUALITY_ASSESSMENT
    else:
        # 使用明确指定的参数
        use_quality_assessment = enable_quality_assessment

    best_result = None
    best_quality = {"score": 0}
    all_attempts = []

    # 定义不同的提取策略 - 优化版：减少策略数量
    if is_grouping_prompt:
        strategies = [
            {
                "name": "智能分组",
                "prompt": EXTRACTION_PROMPT + "\n\n**重要提醒**: 必须返回完整的JSON格式，包含group_name和完整的fileIds数组。",
                "model": model,
                "temperature": 0.1
            }
        ]
    else:
        strategies = [
            {
                "name": "智能提取",
                "prompt": EXTRACTION_PROMPT + "\n\n**重要提醒**: 必须返回完整的JSON格式。",
                "model": model,
                "temperature": 0.1  # 低温度，更确定性的结果
            }
        ]

    for attempt in range(max_attempts):
        strategy = strategies[min(attempt, len(strategies) - 1)]
        logging.info(f"🔄 尝试 {attempt + 1}/{max_attempts}: {strategy['name']}")

        try:
            result = _single_extraction_attempt(
                user_input_content,
                strategy['prompt'],
                strategy['model'],
                strategy.get('temperature', 0.1)
            )

            if result:
                # 根据配置决定是否进行质量评估
                if use_quality_assessment:
                    # 根据提示词类型选择合适的质量评估函数
                    if is_grouping_prompt:
                        quality = evaluate_grouping_quality(result)
                        logging.info(f"📊 {strategy['name']} 智能分组质量评估: 分数={quality.get('score', 0)}, 有效项={quality.get('valid_count', 0)}/{quality.get('total_count', 0)}")
                    else:
                        quality = evaluate_extraction_quality(result)
                        logging.info(f"📊 {strategy['name']} 刮削质量评估: 分数={quality.get('score', 0)}, 有效项={quality.get('valid_count', 0)}/{quality.get('total_count', 0)}")
                else:
                    # 禁用质量评估时，使用默认的高质量分数
                    quality = {"score": 100, "valid_count": 1, "total_count": 1, "valid_ratio": 100}
                    if is_grouping_prompt:
                        logging.info(f"⚡ {strategy['name']} 智能分组质量评估已禁用，直接返回结果")
                    else:
                        logging.info(f"⚡ {strategy['name']} 刮削质量评估已禁用，直接返回结果")

                all_attempts.append({
                    "attempt": attempt + 1,
                    "strategy": strategy['name'],
                    "result": result,
                    "quality": quality
                })

                # 如果禁用质量评估或质量足够好，可以提前返回
                if not use_quality_assessment or (quality.get('score', 0) >= 90 and quality.get('valid_ratio', 0) >= 80):
                    if use_quality_assessment:
                        logging.info(f"✅ {strategy['name']} 达到高质量标准，提前返回")
                    else:
                        logging.info(f"⚡ {strategy['name']} 质量评估已禁用，直接返回第一个结果")
                    return result

                # 更新最佳结果
                if quality.get('score', 0) > best_quality.get('score', 0):
                    best_result = result
                    best_quality = quality
                    if use_quality_assessment:
                        logging.info(f"🎯 更新最佳结果: {strategy['name']} (分数: {quality['score']})")
                    else:
                        logging.info(f"🎯 更新最佳结果: {strategy['name']} (质量评估已禁用)")
            else:
                logging.warning(f"❌ {strategy['name']} 未能提取到有效结果")

        except Exception as e:
            logging.error(f"❌ {strategy['name']} 执行失败: {e}")
            continue

    # 记录所有尝试的总结
    if all_attempts:
        if use_quality_assessment:
            logging.info(f"📋 提取尝试总结:")
            for attempt_info in all_attempts:
                quality = attempt_info.get('quality', {})
                logging.info(f"  - {attempt_info['strategy']}: 分数={quality.get('score', 0)}, 有效率={quality.get('valid_ratio', 0)}%")
        else:
            logging.info(f"📋 提取尝试总结 (质量评估已禁用):")
            for attempt_info in all_attempts:
                logging.info(f"  - {attempt_info['strategy']}: 已完成")

    if best_result:
        if use_quality_assessment:
            logging.info(f"🏆 返回最佳结果，质量分数: {best_quality.get('score', 0)}")
            if best_quality.get('issues'):
                logging.warning(f"⚠️ 质量问题: {best_quality['issues'][:3]}")  # 只显示前3个问题
        else:
            logging.info(f"🏆 返回结果 (质量评估已禁用)")

        # 记录提取总结
        log_extraction_summary(best_result, user_input_content)
    else:
        logging.error(f"❌ 所有提取尝试都失败了")

    return best_result


def _single_extraction_attempt(user_input_content, prompt, model, temperature=0.1):
    """
    单次提取尝试的内部函数，包含JSON解析重试机制
    """
    max_retries = AI_MAX_RETRIES  # 使用全局配置
    retry_delay = AI_RETRY_DELAY  # 使用全局配置

    for retry in range(max_retries):
        try:
            logging.info(f"🔄 AI调用尝试 {retry + 1}/{max_retries}")

            # 构建完整的提示词
            full_prompt = f"{prompt}\n\n{user_input_content}"

            # 使用改进的API调用函数
            response_content = call_ai_api(full_prompt, model, temperature)

            if response_content:
                logging.info(f"✅ AI响应成功，长度: {len(response_content)} 字符")
                # 解析JSON响应
                parsed_result = _parse_ai_response(response_content)
                if parsed_result:
                    logging.info(f"✅ JSON解析成功")
                    return parsed_result
                else:
                    logging.warning(f"⚠️ 重试 {retry + 1}/{max_retries}: JSON解析失败")
            else:
                logging.warning(f"⚠️ 重试 {retry + 1}/{max_retries}: AI响应为空")

            # 如果失败且还有重试机会，等待后重试
            if retry < max_retries - 1:
                logging.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)

        except Exception as e:
            logging.warning(f"❌ 重试 {retry + 1}/{max_retries} 失败: {e}")

    logging.error(f"❌ AI调用最终失败，已尝试 {max_retries} 次")
    return None


def _parse_ai_response(input_string):
    """解析AI响应 - 简化版"""
    # 尝试提取JSON代码块
    logging.info(f"尝试解析AI响应: {input_string}")
    pattern = r'```json(.*?)```'
    match = re.search(pattern, input_string, re.DOTALL)

    if match:
        json_data = match.group(1).strip()
        try:
            return json.loads(json_data)
        except json.JSONDecodeError:
            pass
    # 尝试直接解析整个响应
    input_string = input_string.strip()
    if input_string.startswith(('[', '{')):
        try:
            return json.loads(input_string)
        except json.JSONDecodeError:
            pass

    return None


def search_movie_in_tmdb_enhanced(movie_info, max_strategies=5):
    """
    增强版TMDB搜索函数，支持多种搜索策略和质量评估

    Args:
        movie_info: 电影信息字典
        max_strategies: 最大搜索策略数量

    Returns:
        最佳匹配的TMDB结果
    """
    logging.info(f"🔍 开始增强版TMDB搜索: {movie_info.get('title', 'Unknown')}")

    if not movie_info:
        logging.error("❌ 输入的电影信息为空")
        return None

    try:
        original_title = str(movie_info.get('original_title', ''))
        title = str(movie_info.get('title', ''))
        media_type = str(movie_info.get('media_type', 'movie')).lower()

        # 确定搜索类型
        search_type = 'movie' if media_type == 'movie' else 'tv'

        # 定义多种搜索策略
        search_strategies = [
            {
                "name": "精确匹配",
                "query": original_title,
                "year_tolerance": 0,
                "priority": 1
            },
            {
                "name": "标题变体匹配",
                "query": title if title != original_title else original_title,
                "year_tolerance": 1,
                "priority": 2
            },
            {
                "name": "清理标题匹配",
                "query": re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s]', ' ', original_title).strip(),
                "year_tolerance": 2,
                "priority": 3
            },
            {
                "name": "简化标题匹配",
                "query": _simplify_title(original_title),
                "year_tolerance": 3,
                "priority": 4
            },
            {
                "name": "关键词匹配",
                "query": _extract_keywords(original_title),
                "year_tolerance": 5,
                "priority": 5
            }
        ]

        best_result = None
        best_quality = {"score": 0}
        all_results = []

        for i, strategy in enumerate(search_strategies[:max_strategies]):
            if not strategy["query"] or len(strategy["query"].strip()) < 2:
                logging.info(f"⏭️ 跳过策略 '{strategy['name']}': 查询词太短")
                continue

            logging.info(f"🔍 策略 {i+1}: {strategy['name']} - 查询: '{strategy['query']}'")

            try:
                # 执行TMDB搜索
                search_results = _perform_tmdb_search(strategy["query"], search_type, LANGUAGE)

                if not search_results:
                    logging.info(f"❌ 策略 '{strategy['name']}' 无搜索结果")
                    continue

                # 评估每个搜索结果
                for result in search_results[:5]:  # 只评估前5个结果
                    quality = evaluate_tmdb_match_quality(movie_info, result)

                    # 根据策略优先级调整分数
                    adjusted_score = quality["score"] * (1.0 - (strategy["priority"] - 1) * 0.1)

                    result_info = {
                        "result": result,
                        "quality": quality,
                        "adjusted_score": adjusted_score,
                        "strategy": strategy["name"],
                        "query": strategy["query"]
                    }

                    all_results.append(result_info)

                    # 更新最佳结果
                    if adjusted_score > best_quality.get("score", 0):
                        best_result = result
                        best_quality = quality
                        best_quality["adjusted_score"] = adjusted_score
                        best_quality["strategy"] = strategy["name"]

                        logging.info(f"🎯 更新最佳匹配: {strategy['name']} - 分数: {adjusted_score:.1f}")

                # 如果找到高质量匹配，可以提前返回
                if best_quality.get("adjusted_score", 0) >= 85:
                    logging.info(f"✅ 找到高质量匹配，提前返回")
                    break

            except Exception as e:
                logging.error(f"❌ 策略 '{strategy['name']}' 执行失败: {e}")
                continue

        # 记录搜索结果总结
        if all_results:
            logging.info(f"📊 TMDB搜索总结 (共 {len(all_results)} 个候选结果):")
            # 按分数排序显示前3个结果
            sorted_results = sorted(all_results, key=lambda x: x["adjusted_score"], reverse=True)
            for i, result_info in enumerate(sorted_results[:3]):
                result = result_info["result"]
                title_display = result.get('title') or result.get('name', 'Unknown')
                year_display = (result.get('release_date') or result.get('first_air_date', ''))[:4]
                logging.info(f"  {i+1}. {title_display} ({year_display}) - 分数: {result_info['adjusted_score']:.1f} - 策略: {result_info['strategy']}")

        if best_result:
            title_display = best_result.get('title') or best_result.get('name', 'Unknown')
            year_display = (best_result.get('release_date') or best_result.get('first_air_date', ''))[:4]
            logging.info(f"🏆 最终选择: {title_display} ({year_display}) - 分数: {best_quality.get('adjusted_score', 0):.1f}")
            logging.info(f"🔍 匹配原因: {', '.join(best_quality.get('reasons', []))}")
        else:
            logging.warning(f"❌ 未找到合适的TMDB匹配结果")

        return best_result

    except Exception as e:
        logging.error(f"❌ TMDB搜索过程出错: {e}")
        traceback.print_exc()
        return None


def _perform_tmdb_search(query, media_type_search, language):
    """
    执行单次TMDB API搜索
    """
    if media_type_search == 'movie':
        url = f"{TMDB_API_URL_BASE}/search/movie"
    elif media_type_search == 'tv':
        url = f"{TMDB_API_URL_BASE}/search/tv"
    else:
        return []

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": language,
    }

    max_retries = TMDB_MAX_RETRIES
    retry_delay = TMDB_RETRY_DELAY

    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=TMDB_API_TIMEOUT)
            response.raise_for_status()
            return response.json().get('results', [])
        except requests.RequestException as e:
            logging.warning(f"TMDB API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    return []


def _simplify_title(title):
    """
    简化标题，移除常见的修饰词和标点
    """
    if not title:
        return ""

    # 移除常见的修饰词
    simplified = re.sub(r'\b(the|a|an|and|or|of|in|on|at|to|for|with|by)\b', ' ', title.lower())
    # 移除特殊字符，只保留字母数字和中文
    simplified = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5\s]', ' ', simplified)
    # 移除多余空格
    simplified = re.sub(r'\s+', ' ', simplified).strip()

    return simplified


def _extract_keywords(title):
    """
    从标题中提取关键词
    """
    if not title:
        return ""

    # 移除常见的技术标记
    cleaned = re.sub(r'\b(1080p|720p|4k|bluray|webrip|hdtv|x264|x265|h264|h265)\b', '', title.lower())
    # 提取主要词汇
    words = re.findall(r'[a-zA-Z\u4e00-\u9fa5]{3,}', cleaned)
    # 返回前3个最长的词
    keywords = sorted(set(words), key=len, reverse=True)[:3]

    return ' '.join(keywords)


def extract_movie_name_and_info(chunk):
    """
    优化版电影信息提取和TMDB匹配主函数
    减少重试次数，提高处理速度，添加缓存机制
    """
    qps_limiter.acquire()
    results = []

    # 从文件项对象中提取信息
    fids = [item['fileId'] for item in chunk]
    names = [item['file_path'] for item in chunk]
    sizes = [item['size_gb'] for item in chunk]
    user_input_content = "\n".join(names)

    logging.info(f"🎬 开始处理批次: {len(names)} 个文件")

    # 🚀 检查缓存，避免重复处理
    cached_results = []
    uncached_names = []
    uncached_items = []

    current_time = time.time()

    for fid, name, size in zip(fids, names, sizes):
        cache_key = f"scrape_{hash(name)}"

        if cache_key in scraping_cache:
            cache_entry = scraping_cache[cache_key]
            if current_time - cache_entry['timestamp'] < SCRAPING_CACHE_DURATION:
                # 使用缓存结果
                cached_result = cache_entry['result'].copy()
                cached_result['fileId'] = fid  # 更新文件ID
                cached_results.append(cached_result)
                logging.debug(f"💾 使用缓存结果: {os.path.basename(name)}")
                continue

        # 需要重新处理的文件
        uncached_names.append(name)
        uncached_items.append({'fileId': fid, 'file_path': name, 'size_gb': size})

    if cached_results:
        logging.info(f"💾 从缓存获得 {len(cached_results)} 个结果")
        results.extend(cached_results)

    if not uncached_names:
        logging.info("✅ 所有文件都有缓存，无需重新处理")
        return results

    logging.info(f"🔄 需要重新处理 {len(uncached_names)} 个文件")
    user_input_content = "\n".join(uncached_names)

    # 🚀 优化：减少重试次数从3次到2次，提高速度
    movie_info = extract_movie_info_from_filename_enhanced(
        user_input_content,
        EXTRACTION_PROMPT,
        max_attempts=3  # 从3减少到2，平衡准确性和速度
    )

    if not movie_info:
        logging.warning("❌ 没有从文件名中提取到任何电影信息")
        # 为每个文件创建失败结果
        for fid, original_filename, size in zip(fids, names, sizes):
            results.append({
                'fileId': fid,
                'original_name': os.path.basename(original_filename),
                'suggested_name': '',
                'size': size,
                'tmdb_info': None,
                'file_info': None,
                'status': 'extraction_failed'
            })
        return results

    logging.info(f"✅ 成功提取 {len(movie_info)} 个文件的信息")

    # 🚀 并行处理每个文件的信息
    def process_single_file(args):
        """处理单个文件的TMDB搜索和命名"""
        i, fid, file_info, size, original_filename = args
        file_basename = os.path.basename(original_filename)
        logging.info(f"🔄 处理文件 {i+1}/{len(fids)}: {file_basename}")

        # 为 file_info 添加 file_name 字段，用于后续处理
        if isinstance(file_info, dict):
            file_info['file_name'] = original_filename
        else:
            logging.warning(f"⚠️ 文件 {file_basename} 的提取信息格式异常")
            return {
                'fileId': fid,
                'original_name': file_basename,
                'suggested_name': '',
                'size': size,
                'tmdb_info': None,
                'file_info': file_info,
                'status': 'invalid_info'
            }

        try:
            # 🎯 检查是否包含TMDB ID，如果有则优先验证但仍进行搜索
            tmdb_id = file_info.get('tmdb_id', '')
            if tmdb_id and tmdb_id.isdigit():
                logging.info(f"🎯 发现TMDB ID: {tmdb_id}，将进行搜索验证")
                # 从TMDB API获取详细信息进行验证
                media_type = file_info.get('media_type', 'movie')

                try:
                    # 根据媒体类型调用相应的TMDB API
                    if media_type in ['tv', 'tv_show', 'anime']:
                        url = f"{TMDB_API_URL_BASE}/tv/{tmdb_id}"
                    else:
                        url = f"{TMDB_API_URL_BASE}/movie/{tmdb_id}"

                    params = {
                        "api_key": TMDB_API_KEY,
                        "language": LANGUAGE,
                    }

                    response = requests.get(url, params=params, timeout=TMDB_API_TIMEOUT)
                    response.raise_for_status()
                    tmdb_candidate = response.json()

                    # 验证这个TMDB ID是否与文件信息匹配
                    candidate_title = tmdb_candidate.get('name') or tmdb_candidate.get('title', '')
                    file_title = file_info.get('title', '')

                    # 简单的标题匹配验证
                    if candidate_title and file_title:
                        title_similarity = len(set(candidate_title.lower().split()) & set(file_title.lower().split()))
                        if title_similarity >= 1:  # 至少有一个共同词汇
                            logging.info(f"✅ TMDB ID {tmdb_id} 验证通过: {candidate_title}")
                            tmdb_result = tmdb_candidate
                        else:
                            logging.warning(f"⚠️ TMDB ID {tmdb_id} 验证失败，标题不匹配: '{candidate_title}' vs '{file_title}'，将进行搜索")
                            tmdb_result = None
                    else:
                        logging.info(f"✅ 使用TMDB ID {tmdb_id}: {candidate_title}")
                        tmdb_result = tmdb_candidate

                except Exception as e:
                    logging.warning(f"⚠️ 无法验证TMDB ID {tmdb_id}: {e}，将进行搜索")
                    tmdb_result = None
            else:
                tmdb_result = None

            # 如果没有有效的TMDB结果，进行搜索
            if not tmdb_result:
                # 使用增强版TMDB搜索函数
                logging.info(f"🔍 开始TMDB搜索: {file_info.get('title', 'Unknown')}")
                tmdb_result = search_movie_in_tmdb_enhanced(file_info, max_strategies=5)
            _, ext = os.path.splitext(original_filename)

            if tmdb_result:
                # 评估匹配质量
                match_quality = evaluate_tmdb_match_quality(file_info, tmdb_result)
                logging.info(f"📊 TMDB匹配质量: {match_quality['score']:.1f}分")

                # 根据媒体类型确定命名格式
                media_type = file_info.get('media_type', 'movie')
                suggested_name = ""

                if media_type in ['movie']:
                    # 电影命名格式: Title (Year) {tmdb-id} size.ext
                    title = tmdb_result.get('title', 'Unknown')
                    release_date = tmdb_result.get('release_date', '0000-01-01')
                    tmdb_id = tmdb_result.get('id', 'unknown')
                    suggested_name = f"{title} ({release_date[:4]}) {{tmdb-{tmdb_id}}} {size}{ext}".replace('/', '')
                else:
                    # 电视剧命名格式: Title (Year) S##E## {tmdb-id} size.ext
                    title = tmdb_result.get('name', 'Unknown')
                    first_air_date = tmdb_result.get('first_air_date', '0000-01-01')
                    tmdb_id = tmdb_result.get('id', 'unknown')

                    # 调试日志：输出TMDB结果的详细信息
                    logging.debug(f"🔍 TMDB结果详情: name='{tmdb_result.get('name')}', first_air_date='{tmdb_result.get('first_air_date')}', id='{tmdb_result.get('id')}'")
                    logging.debug(f"🔍 提取的标题信息: title='{title}', first_air_date='{first_air_date}', tmdb_id='{tmdb_id}'")

                    # 确保 season 和 episode 是整数，如果为 None 或其他非数字类型，则默认为 1
                    season = int(file_info.get('season', 1) or 1)
                    episode = int(file_info.get('episode', 1) or 1)

                    if file_info.get('episode') is not None:  # 只有当有剧集信息时才生成建议名称
                        suggested_name = f"{title} ({first_air_date[:4]}) S{season:02d}E{episode:02d} {{tmdb-{tmdb_id}}} {size}{ext}".replace('/', '')
                    else:
                        suggested_name = ""  # 如果没有剧集信息，则不生成建议名称

                if suggested_name:
                    sanitized_output_string = sanitize_filename(suggested_name)
                    logging.info(f"✅ 成功生成建议名称: {file_basename} -> {sanitized_output_string}")

                    return {
                        'fileId': fid,
                        'original_name': file_basename,
                        'suggested_name': sanitized_output_string,
                        'size': size,
                        'tmdb_info': tmdb_result,
                        'file_info': file_info,
                        'match_quality': match_quality,
                        'status': 'success'
                    }
                else:
                    # 没有生成建议名称（通常是电视剧缺少剧集信息）
                    logging.warning(f"⚠️ 未能为 {file_basename} 生成建议名称（可能缺少剧集信息）")
                    return {
                        'fileId': fid,
                        'original_name': file_basename,
                        'suggested_name': '',
                        'size': size,
                        'tmdb_info': tmdb_result,
                        'file_info': file_info,
                        'match_quality': match_quality,
                        'status': 'no_episode_info'
                    }
            else:
                logging.warning(f"❌ 未找到 {file_basename} 的TMDB匹配结果")
                return {
                    'fileId': fid,
                    'original_name': file_basename,
                    'suggested_name': '',
                    'size': size,
                    'tmdb_info': None,
                    'file_info': file_info,
                    'status': 'no_match'
                }

        except Exception as exc:
            logging.error(f"❌ 处理文件 {file_basename} 时发生异常: {exc}")
            traceback.print_exc()
            return {
                'fileId': fid,
                'original_name': file_basename,
                'suggested_name': '',
                'size': size,
                'tmdb_info': None,
                'file_info': file_info,
                'status': 'error',
                'error': str(exc)
            }

    # 准备并行处理的参数
    file_args = [(i, fid, file_info, size, original_filename)
                 for i, (fid, file_info, size, original_filename)
                 in enumerate(zip(fids, movie_info, sizes, names))]

    # 使用线程池并行处理
    from concurrent.futures import ThreadPoolExecutor, as_completed
    max_workers = min(len(file_args), MAX_WORKERS)  # 使用配置的最大工作线程数

    logging.info(f"🚀 开始并行处理 {len(file_args)} 个文件，使用 {max_workers} 个线程")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_args = {executor.submit(process_single_file, args): args for args in file_args}

        # 收集结果并更新缓存
        for future in as_completed(future_to_args):
            try:
                result = future.result()
                results.append(result)

                # 更新缓存（只缓存成功的结果）
                if result['status'] == 'success':
                    args = future_to_args[future]
                    original_filename = args[4]
                    cache_key = f"scrape_{hash(original_filename)}"
                    scraping_cache[cache_key] = {
                        'result': result.copy(),
                        'timestamp': current_time
                    }

            except Exception as exc:
                args = future_to_args[future]
                file_basename = os.path.basename(args[4])
                logging.error(f"❌ 并行处理文件 {file_basename} 时发生异常: {exc}")
                results.append({
                    'fileId': args[1],
                    'original_name': file_basename,
                    'suggested_name': '',
                    'size': args[3],
                    'tmdb_info': None,
                    'file_info': args[2],
                    'status': 'error',
                    'error': str(exc)
                })

    # 统计处理结果并记录详细总结
    success_count = len([r for r in results if r['status'] == 'success'])
    total_count = len(results)
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0

    logging.info(f"🎯 批次处理完成: {success_count}/{total_count} 成功 ({success_rate:.1f}%)")

    # 记录TMDB搜索总结
    log_tmdb_search_summary(results)

    # 🚀 保存新处理的结果到缓存
    current_time = time.time()
    for result in results:
        if result['fileId'] in [item['fileId'] for item in uncached_items]:
            # 只缓存新处理的结果
            original_name = result['original_name']
            cache_key = f"scrape_{hash(original_name)}"

            # 创建缓存条目（不包含fileId，因为fileId可能变化）
            cache_result = result.copy()
            del cache_result['fileId']

            scraping_cache[cache_key] = {
                'result': cache_result,
                'timestamp': current_time
            }
            logging.debug(f"💾 缓存结果: {original_name}")

    # LRU缓存会自动清理过期条目，无需手动清理
    # 这里只记录一下缓存状态
    cache_stats = scraping_cache.stats()
    logging.debug(f"🧹 刮削缓存状态: {cache_stats['size']}/{cache_stats['max_size']} 项")

    return results



# ================================
# 应用程序启动初始化
# ================================

# 初始化日志系统
initialize_logging_system()

# 加载应用配置
load_application_config()

# 初始化123云盘访问令牌
access_token = initialize_access_token()
if access_token:
    logging.info(f"✅ 123云盘访问令牌已初始化: {access_token[:10]}***")
else:
    logging.info("⚠️ 123云盘访问令牌未设置，请在配置页面设置CLIENT_ID和CLIENT_SECRET")

# 初始化QPS限制器
initialize_qps_limiters()

# Flask 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    # 返回所有当前存储的日志
    return jsonify(list(log_queue))

@app.route('/config', methods=['GET'])
def get_config():
    """返回当前配置。"""
    return jsonify(app_config)

@app.route('/token_status', methods=['GET'])
def get_token_status():
    """返回访问令牌状态信息"""
    global access_token, access_token_expires_at

    try:
        if not access_token:
            return jsonify({
                'has_token': False,
                'is_expired': True,
                'expires_at': None,
                'remaining_time': None,
                'message': '未设置访问令牌'
            })

        # 检查令牌是否过期
        is_expired = is_access_token_expired()

        # 计算剩余时间
        remaining_time = None
        expires_at_str = None
        if access_token_expires_at:
            expires_at_str = access_token_expires_at.strftime('%Y-%m-%d %H:%M:%S')
            if not is_expired:
                remaining_time = str(access_token_expires_at - datetime.datetime.now())

        return jsonify({
            'has_token': True,
            'is_expired': is_expired,
            'expires_at': expires_at_str,
            'remaining_time': remaining_time,
            'message': '访问令牌已过期' if is_expired else '访问令牌有效'
        })

    except Exception as e:
        logging.error(f"获取令牌状态时发生错误: {e}")
        return jsonify({
            'has_token': bool(access_token),
            'is_expired': True,
            'expires_at': None,
            'remaining_time': None,
            'message': f'检查令牌状态时发生错误: {str(e)}'
        })

@app.route('/refresh_token', methods=['POST'])
def refresh_token():
    """手动刷新访问令牌"""
    try:
        success = refresh_access_token_if_needed()

        if success:
            # 获取新令牌的状态信息
            expires_at_str = None
            remaining_time = None
            if access_token_expires_at:
                expires_at_str = access_token_expires_at.strftime('%Y-%m-%d %H:%M:%S')
                remaining_time = str(access_token_expires_at - datetime.datetime.now())

            return jsonify({
                'success': True,
                'message': '访问令牌刷新成功',
                'expires_at': expires_at_str,
                'remaining_time': remaining_time
            })
        else:
            return jsonify({
                'success': False,
                'message': '访问令牌刷新失败，请检查CLIENT_ID和CLIENT_SECRET配置'
            })

    except Exception as e:
        logging.error(f"手动刷新访问令牌时发生错误: {e}")
        return jsonify({
            'success': False,
            'message': f'刷新访问令牌时发生错误: {str(e)}'
        })



@app.route('/test_ai_api', methods=['POST'])
def test_ai_api():
    """测试AI API连接"""
    try:
        # 获取当前配置（支持新旧配置字段）
        api_url = app_config.get("AI_API_URL", "") or app_config.get("GEMINI_API_URL", "")
        api_key = app_config.get("AI_API_KEY", "") or app_config.get("GEMINI_API_KEY", "")
        grouping_model = app_config.get("GROUPING_MODEL", "")

        # 检查基本配置
        if not api_url:
            return jsonify({
                'success': False,
                'error': 'GEMINI_API_URL 未配置',
                'details': {
                    'api_url': api_url,
                    'model': grouping_model,
                    'api_key_status': '已设置' if api_key else '未设置'
                }
            })

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'GEMINI_API_KEY 未配置',
                'details': {
                    'api_url': api_url,
                    'model': grouping_model,
                    'api_key_status': '未设置'
                }
            })

        if not grouping_model:
            return jsonify({
                'success': False,
                'error': 'GROUPING_MODEL 未配置',
                'details': {
                    'api_url': api_url,
                    'model': grouping_model,
                    'api_key_status': '已设置'
                }
            })

        # 测试基础API连接
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 简单的测试请求
        test_payload = {
            "model": grouping_model,
            "messages": [
                {
                    "role": "user",
                    "content": "请回复'AI连接测试成功'"
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        logging.info(f"🧪 测试AI API连接: {api_url}")
        logging.info(f"🤖 使用模型: {grouping_model}")

        response = requests.post(api_url, headers=headers, json=test_payload, timeout=AI_API_TIMEOUT)

        if response.status_code == 200:
            response_data = response.json()
            basic_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '无响应')

            # 测试智能分组功能
            grouping_test_payload = {
                "model": grouping_model,
                "messages": [
                    {
                        "role": "user",
                        "content": """请分析以下文件名并返回JSON格式的分组建议：
文件列表：
1. 复仇者联盟1.mkv
2. 复仇者联盟2.mkv
3. 钢铁侠1.mkv

请返回JSON格式：
{
  "groups": [
    {
      "name": "复仇者联盟系列",
      "files": ["复仇者联盟1.mkv", "复仇者联盟2.mkv"]
    }
  ]
}"""
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.1
            }

            grouping_response = requests.post(api_url, headers=headers, json=grouping_test_payload, timeout=AI_API_TIMEOUT)
            grouping_result = "分组测试失败"

            if grouping_response.status_code == 200:
                grouping_data = grouping_response.json()
                grouping_result = grouping_data.get('choices', [{}])[0].get('message', {}).get('content', '无响应')

            return jsonify({
                'success': True,
                'details': {
                    'api_url': api_url,
                    'model': grouping_model,
                    'api_key_status': '已设置',
                    'basic_response': basic_response,
                    'grouping_response': grouping_result
                }
            })
        else:
            error_text = response.text
            return jsonify({
                'success': False,
                'error': f'API请求失败 (HTTP {response.status_code}): {error_text}',
                'details': {
                    'api_url': api_url,
                    'model': grouping_model,
                    'api_key_status': '已设置'
                }
            })

    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'API请求超时，请检查网络连接和服务器状态',
            'details': {
                'api_url': app_config.get("GEMINI_API_URL", ""),
                'model': app_config.get("GROUPING_MODEL", ""),
                'api_key_status': '已设置' if app_config.get("GEMINI_API_KEY") else '未设置'
            }
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'API连接失败，请检查GEMINI_API_URL是否正确',
            'details': {
                'api_url': app_config.get("AI_API_URL", "") or app_config.get("GEMINI_API_URL", ""),
                'model': app_config.get("GROUPING_MODEL", ""),
                'api_key_status': '已设置' if (app_config.get("AI_API_KEY") or app_config.get("GEMINI_API_KEY")) else '未设置'
            }
        })
    except Exception as e:
        logging.error(f"❌ AI API测试失败: {e}")
        return jsonify({
            'success': False,
            'error': f'测试过程中发生错误: {str(e)}',
            'details': {
                'api_url': app_config.get("AI_API_URL", "") or app_config.get("GEMINI_API_URL", ""),
                'model': app_config.get("GROUPING_MODEL", ""),
                'api_key_status': '已设置' if (app_config.get("AI_API_KEY") or app_config.get("GEMINI_API_KEY")) else '未设置'
            }
        })


@app.route('/save_config', methods=['POST'])
def save_configuration():
    """保存用户提交的配置。"""
    global app_config, QPS_LIMIT, CHUNK_SIZE, MAX_WORKERS, CLIENT_ID, CLIENT_SECRET
    global TMDB_API_KEY, AI_API_KEY, AI_API_URL, MODEL, GROUPING_MODEL, LANGUAGE
    global CURRENT_STORAGE_TYPE, STORAGE_CONFIG
    try:
        new_config_data = request.json
        logging.info(f"接收到新的配置数据: {new_config_data}")

        # 验证并更新配置
        if "QPS_LIMIT" in new_config_data:
            app_config["QPS_LIMIT"] = int(new_config_data["QPS_LIMIT"])
        if "CHUNK_SIZE" in new_config_data:
            app_config["CHUNK_SIZE"] = int(new_config_data["CHUNK_SIZE"])
        if "MAX_WORKERS" in new_config_data:
            app_config["MAX_WORKERS"] = int(new_config_data["MAX_WORKERS"])
        if "CLIENT_ID" in new_config_data:
            app_config["CLIENT_ID"] = new_config_data["CLIENT_ID"]
        if "CLIENT_SECRET" in new_config_data:
            app_config["CLIENT_SECRET"] = new_config_data["CLIENT_SECRET"]

        if "TMDB_API_KEY" in new_config_data:
            app_config["TMDB_API_KEY"] = new_config_data["TMDB_API_KEY"]
        if "GEMINI_API_KEY" in new_config_data:
            app_config["GEMINI_API_KEY"] = new_config_data["GEMINI_API_KEY"]
        if "GEMINI_API_URL" in new_config_data:
            app_config["GEMINI_API_URL"] = new_config_data["GEMINI_API_URL"]
        if "MODEL" in new_config_data:
            app_config["MODEL"] = new_config_data["MODEL"]
        if "GROUPING_MODEL" in new_config_data:
            app_config["GROUPING_MODEL"] = new_config_data["GROUPING_MODEL"]
        if "LANGUAGE" in new_config_data:
            app_config["LANGUAGE"] = new_config_data["LANGUAGE"]

        # 云盘配置
        if "STORAGE_TYPE" in new_config_data:
            app_config["STORAGE_TYPE"] = new_config_data["STORAGE_TYPE"]
        if "PAN115_COOKIE" in new_config_data:
            app_config["PAN115_COOKIE"] = new_config_data["PAN115_COOKIE"]

        # 保存配置到文件
        save_application_config()

        # 重新创建云盘服务实例
        CURRENT_STORAGE_TYPE = app_config.get("STORAGE_TYPE", "123pan")
        STORAGE_CONFIG = {
            "123pan": {
                "client_id": app_config.get("CLIENT_ID"),
                "client_secret": app_config.get("CLIENT_SECRET")
            },
            "115pan": {
                "cookie": app_config.get("PAN115_COOKIE")
            }
        }
        # cloud_service = create_cloud_service()  # 暂时注释掉，当前只使用123云盘

        # 重新加载所有配置和相关全局变量
        load_application_config()

        # 确保所有QPS限制器都更新
        global qps_limiter, v2_list_limiter, rename_limiter, move_limiter, delete_limiter
        qps_limiter = QPSLimiter(qps_limit=app_config["QPS_LIMIT"])  # 通用限制器，使用配置值
        v2_list_limiter = QPSLimiter(qps_limit=4)     # api/v2/file/list: 4 QPS (平衡性能和稳定性)
        rename_limiter = QPSLimiter(qps_limit=1)       # api/v1/file/rename: 保守使用1 QPS
        move_limiter = QPSLimiter(qps_limit=3)        # api/v1/file/move: 3 QPS (提高性能)
        delete_limiter = QPSLimiter(qps_limit=2)       # api/v1/file/delete: 2 QPS (提高性能)

        logging.info("配置已更新并应用。")
        return jsonify({'success': True, 'message': '配置保存成功并已应用。'})
    except Exception as e:
        logging.error(f"保存配置时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'保存配置时发生错误: {str(e)}'})



@app.route('/get_folder_content/<int:folder_id>', methods=['GET'])
def get_folder_content_by_id(folder_id):
    """通过GET方法获取指定文件夹下的文件和文件夹列表（用于文件夹浏览器，带缓存优化）"""
    try:
        logging.info(f"📂 获取文件夹 {folder_id} 下的内容")

        # 🚀 检查缓存（使用不同的缓存键以区分GET和POST请求）
        cache_key_suffix = "_folders_only"
        cached_content = get_cached_folder_content(f"{folder_id}{cache_key_suffix}")
        if cached_content is not None:
            logging.info(f"⚡ 使用缓存的目录内容（仅文件夹），跳过API调用")
            return jsonify(cached_content)

        limit = 100
        paths = []
        fid = folder_id
        if fid == 0:
            paths.append({"fileID": 0, "filename": "根目录", "parentFileID": 0})
        else:
            while True:
                folder_details = detail(fid)
                fid = int(folder_details["parentFileID"])
                paths.append(folder_details)
                if fid == 0:
                    paths.append({"fileID": 0, "filename": "根目录", "parentFileID": 0})
                    break

        paths.reverse()
        # logging.info(f"paths: {paths}")
        current_path_parts = [a['filename'] for a in paths[1:]]
        current_path_prefix = "/".join(current_path_parts)
        logging.info(f"current_path_prefix: {current_path_prefix}")
        folder_content = get_all_files_in_folder(folder_id, limit=limit)
        # logging.info(folder_content)

        # 只返回文件夹，不返回文件（用于文件夹浏览器）
        folders = []
        for item in folder_content:
            if item['type'] == 1:  # 只处理文件夹
                folders.append({
                    'filename': item['filename'],
                    'fileId': item['fileId'],
                    'parentFileId': item['parentFileId'],
                    'file_name': item.get('file_name', os.path.join(current_path_prefix, item['filename']))
                })

        # 构建路径信息
        path_info = {
            'path_parts': [{'id': path['fileID'], 'name': path['filename']} for path in paths],
            'parent_id': paths[-2]['fileID'] if len(paths) > 1 else 0
        }

        logging.info(f"📁 找到 {len(folders)} 个文件夹")

        # 构建响应数据
        response_data = {
            'success': True,
            'folders': folders,
            'path_info': path_info,
            'current_folder_id': folder_id
        }

        # 🚀 缓存响应数据（仅文件夹）
        cache_key = f"folder_{folder_id}_folders_only"
        cache_folder_content(cache_key, response_data)

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"获取文件夹内容时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_folder_content', methods=['POST'])
def get_folder_content():
    """获取指定文件夹下的文件和文件夹列表（带缓存优化）"""
    try:
        # 重置任务状态，避免之前的取消状态影响普通浏览
        reset_task_state()

        folder_id = request.form.get('folder_id', '0')
        limit = int(request.form.get('limit', 100))
        folder_id = int(folder_id)

        logging.info(f"📂 获取文件夹 {folder_id} 下的内容")

        # 🚀 检查缓存
        cached_content = get_cached_folder_content(folder_id)
        if cached_content is not None:
            logging.info(f"⚡ 使用缓存的目录内容，跳过API调用")
            return jsonify(cached_content)

        paths = []
        fid = folder_id
        if fid == 0:
            paths.append({"fileID": 0, "filename": "根目录", "parentFileID": 0})
        else:
            while True:
                folder_details = detail(fid)
                # fileID = folder_details["fileID"]
                # filename = folder_details["filename"]
                fid = int(folder_details["parentFileID"])
                paths.append(folder_details)
                if fid == 0:
                    paths.append({"fileID": 0, "filename": "根目录", "parentFileID": 0})
                    break 

        paths.reverse()
        # logging.info(f"paths: {paths}")
        current_path_parts = [a['filename'] for a in paths[1:]]
        current_path_prefix = "/".join(current_path_parts)
        # logging.info(f"📂 文件夹路径 : {current_path_prefix}")
        folder_content = get_all_files_in_folder(folder_id, limit=limit)
        # logging.info(folder_content)



        all_files_and_folders = []
        for item in folder_content:
            if item['type'] == 1:  # 文件夹
                all_files_and_folders.append({
                    'name': item['filename'],
                    'is_dir': True,
                    'fileId': item['fileId'],
                    'parentFileId': item['parentFileId'],
                    'file_name': item.get('file_name', os.path.join(current_path_prefix, item['filename']))
                })

            elif item['type'] == 0:  # 文件
                _, ext = os.path.splitext(item['filename'])
                if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                    bytes_value = item['size']
                    gb_in_bytes = 1024 ** 3
                    gb_value = bytes_value / gb_in_bytes
                    size_str = f"{gb_value:.1f}GB"

                    all_files_and_folders.append({
                        'name': item['filename'],
                        'is_dir': False,
                        'fileId': item['fileId'],
                        'parentFileId': item['parentFileId'],
                        'size': size_str,
                        'file_name': item.get('file_name', os.path.join(current_path_prefix, item['filename']))

                    })


        current_path = "/" + "/".join([part['filename'] for part in paths[1:]])
        if current_path == "/":
            current_path = "/根目录"

        if len(paths) < 2:
            parent_folder_id = '0'
        else:
            parent_folder_id = str(paths[-2]['fileID'])

        logging.info(f"📄 找到 {len(all_files_and_folders)} 个项目")
        logging.info(f"📍 当前路径: {current_path}")
        logging.info(f"⬆️ 父文件夹ID: {parent_folder_id}")

        # 构建响应数据
        response_data = {
            'success': True,
            'current_folder_id': str(folder_id),
            'parent_folder_id': parent_folder_id,
            'current_path': current_path,
            'files_and_folders': all_files_and_folders,
            'total_count': len(all_files_and_folders),
            'path_parts': [{'name': path['filename'], 'fileId': str(path['fileID'])} for path in paths]
        }

        # 🚀 缓存响应数据（只缓存成功的结果）
        cache_folder_content(folder_id, response_data)

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"获取文件夹内容时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/get_folder_info', methods=['GET'])
def get_folder_info():
    """获取单个文件夹的基本信息（轻量级，用于点击查看）"""
    try:
        folder_id = request.args.get('folder_id', '0')

        # 验证文件夹ID
        folder_id, error_msg = validate_folder_id(folder_id)
        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        logging.info(f"🔍 获取文件夹 {folder_id} 的基本信息")

        # 只获取直接子项，不递归，提高速度
        try:
            folder_content = get_file_list_from_cloud(folder_id, limit=100)
            if not folder_content or 'fileList' not in folder_content:
                return jsonify({'success': False, 'error': '无法获取文件夹内容'})

            files = folder_content['fileList']

            # 统计基本信息
            total_items = len(files)
            folder_count = sum(1 for item in files if item.get('type') == 1)
            file_count = sum(1 for item in files if item.get('type') == 0)
            video_count = 0
            total_size = 0

            # 统计视频文件和大小
            for item in files:
                if item.get('type') == 0:  # 文件
                    file_size = item.get('size', 0)
                    if isinstance(file_size, (int, float)):
                        total_size += file_size

                    # 检查是否为视频文件
                    filename = item.get('filename', '')
                    _, ext = os.path.splitext(filename)
                    if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                        video_count += 1

            # 格式化大小
            if total_size >= 1024 ** 4:  # TB
                size_str = f"{total_size / (1024 ** 4):.1f}TB"
            elif total_size >= 1024 ** 3:  # GB
                size_str = f"{total_size / (1024 ** 3):.1f}GB"
            elif total_size >= 1024 ** 2:  # MB
                size_str = f"{total_size / (1024 ** 2):.1f}MB"
            elif total_size >= 1024:  # KB
                size_str = f"{total_size / 1024:.1f}KB"
            else:
                size_str = f"{int(total_size)}B"

            # 获取文件夹路径
            folder_path = get_folder_full_path(folder_id)

            result = {
                'success': True,
                'folder_id': folder_id,
                'folder_path': folder_path,
                'total_items': total_items,
                'folder_count': folder_count,
                'file_count': file_count,
                'video_count': video_count,
                'size': size_str,
                'total_size_bytes': int(total_size)
            }

            logging.info(f"📊 文件夹 {folder_id} 信息: {total_items} 项目 ({folder_count} 文件夹, {file_count} 文件, {video_count} 视频), 大小 {size_str}")
            return jsonify(result)

        except Exception as e:
            logging.error(f"获取文件夹内容失败: {e}")
            return jsonify({'success': False, 'error': f'获取文件夹内容失败: {str(e)}'})

    except Exception as e:
        logging.error(f"获取文件夹信息时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_folder_properties', methods=['POST'])
def get_folder_properties():
    """获取文件夹基本属性（文件数量和总大小）- 快速版本"""
    try:
        folder_id = request.form.get('folder_id', '0')
        include_grouping = request.form.get('include_grouping', 'false').lower() == 'true'

        # 处理无效的folder_id值
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '文件夹ID必须是数字'})

        logging.info(f"🔍 获取文件夹 {folder_id} 的基本属性")

        if include_grouping:
            # 🚀 使用新的任务队列系统进行智能分组
            try:
                # 检查任务管理器是否可用
                if grouping_task_manager is None:
                    return jsonify({
                        'success': False,
                        'error': '任务管理器未初始化，请检查系统状态',
                        'task_queue_error': True
                    })

                # 获取文件夹名称
                folder_name = request.form.get('folder_name', f'文件夹{folder_id}')

                # 提交任务到队列
                task_id = grouping_task_manager.submit_task(folder_id, folder_name)

                return jsonify({
                    'success': True,
                    'use_task_queue': True,
                    'task_id': task_id,
                    'message': f'智能分组任务已提交到队列 (任务ID: {task_id})'
                })

            except ValueError as e:
                # 如果是重复任务或队列满的错误，返回相应信息
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'task_queue_error': True
                })
        else:
            # 🔍 只获取基本文件信息，不进行智能分组
            video_files = []
            try:
                get_video_files_recursively(folder_id, video_files)
            except Exception as e:
                logging.error(f"递归获取视频文件时发生错误: {e}")
                return jsonify({'success': False, 'error': f'获取文件列表失败: {str(e)}'})

            return jsonify({
                'success': True,
                'count': len(video_files),
                'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB",
                'video_files': video_files
            })

    except Exception as e:
        logging.error(f"获取文件夹属性时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/get_folder_grouping_analysis', methods=['POST'])
def get_folder_grouping_analysis():
    """获取文件夹的智能分组分析 - 详细版本"""
    # 用于收集处理过程信息的列表
    process_logs = []

    def add_process_log(message, level='info'):
        """添加处理过程日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        process_logs.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })
        # 同时记录到系统日志
        if level == 'error':
            logging.error(message)
        elif level == 'warning':
            logging.warning(message)
        else:
            logging.info(message)

    try:
        # 开始新任务
        task_id = f"folder_grouping_{int(time.time())}"
        start_new_task(task_id)
        add_process_log(f"🚀 开始新任务: {task_id}")

        folder_id = request.form.get('folder_id', '0')

        # 处理无效的folder_id值
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            add_process_log("❌ 无效的文件夹ID", 'error')
            return jsonify({'success': False, 'error': '无效的文件夹ID', 'process_logs': process_logs})

        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            add_process_log("❌ 文件夹ID必须是数字", 'error')
            return jsonify({'success': False, 'error': '文件夹ID必须是数字', 'process_logs': process_logs})

        add_process_log(f"🔍 开始分析文件夹 {folder_id} 的智能分组")

        # 检查任务是否被取消
        try:
            check_task_cancelled()
        except Exception as e:
            if "任务已被用户取消" in str(e):
                add_process_log("🛑 任务被用户取消", 'warning')
                return jsonify({'success': False, 'error': '任务已被用户取消', 'cancelled': True, 'process_logs': process_logs})

        # 递归获取文件夹中的所有视频文件
        video_files = []
        try:
            add_process_log(f"📂 开始扫描文件夹 {folder_id} 中的视频文件")
            get_video_files_recursively(folder_id, video_files)
            add_process_log(f"✅ 扫描完成，发现 {len(video_files)} 个视频文件")
        except Exception as e:
            add_process_log(f"❌ 递归获取视频文件时发生错误: {e}", 'error')
            return jsonify({'success': False, 'error': f'获取文件列表失败: {str(e)}', 'process_logs': process_logs})

        # 调用内部分组分析函数
        try:
            grouping_result = get_folder_grouping_analysis_internal(video_files, folder_id, add_process_log)
            grouping_result['process_logs'] = process_logs
            return jsonify(grouping_result)
        except Exception as e:
            add_process_log(f"❌ 分组分析失败: {e}", 'error')
            return jsonify({'success': False, 'error': str(e), 'process_logs': process_logs})



    except Exception as e:
        if "任务已被用户取消" in str(e):
            add_process_log("🛑 智能分组任务被用户取消", 'warning')
            return jsonify({'success': False, 'error': '任务已被用户取消', 'cancelled': True, 'process_logs': process_logs})
        else:
            add_process_log(f"❌ 分组分析时发生错误: {e}", 'error')
            return jsonify({'success': False, 'error': str(e), 'process_logs': process_logs})

def _calculate_total_size(video_files):
    """计算文件总大小"""
    total_bytes = 0
    for file_item in video_files:
        try:
            size_str = file_item.get('size_gb', '')
            if not size_str:
                continue

            # 解析不同单位的文件大小
            if 'GB' in size_str:
                total_bytes += float(size_str.replace('GB', '')) * (1024 ** 3)
            elif 'MB' in size_str:
                total_bytes += float(size_str.replace('MB', '')) * (1024 ** 2)
            elif 'KB' in size_str:
                total_bytes += float(size_str.replace('KB', '')) * 1024
            elif size_str.isdigit():
                total_bytes += int(size_str)
        except (ValueError, KeyError):
            continue
    return total_bytes


def _format_file_size(size_bytes):
    """格式化文件大小"""
    units = [(1024**4, 'TB'), (1024**3, 'GB'), (1024**2, 'MB'), (1024, 'KB')]
    for threshold, unit in units:
        if size_bytes >= threshold:
            return f"{size_bytes / threshold:.1f}{unit}"
    return f"{int(size_bytes)}B"





# 🔄 智能分组缓存管理函数
def generate_cache_key(video_files, folder_id):
    """生成缓存键"""
    # 使用文件夹ID和文件列表的哈希值作为缓存键
    file_info = []
    for file in video_files:
        file_info.append(f"{file['filename']}_{file.get('fileID', '')}")

    file_hash = hashlib.md5('|'.join(sorted(file_info)).encode('utf-8')).hexdigest()
    return f"grouping_{folder_id}_{file_hash}"

def get_cached_grouping_result(cache_key):
    """获取缓存的分组结果"""
    global grouping_cache

    if cache_key not in grouping_cache:
        return None

    cached_data = grouping_cache[cache_key]
    cache_time = cached_data.get('timestamp', 0)
    current_time = time.time()

    # 检查缓存是否过期
    if current_time - cache_time > GROUPING_CACHE_DURATION:
        # 缓存过期，删除并返回None
        del grouping_cache[cache_key]
        logging.info(f"🗑️ 缓存已过期并清理: {cache_key}")
        return None

    logging.info(f"🎯 命中缓存: {cache_key}, 剩余有效期: {int(GROUPING_CACHE_DURATION - (current_time - cache_time))}秒")
    return cached_data.get('result')

def cache_grouping_result(cache_key, result):
    """缓存分组结果"""
    global grouping_cache

    grouping_cache[cache_key] = {
        'timestamp': time.time(),
        'result': result
    }

    logging.info(f"💾 缓存分组结果: {cache_key}")

    # 清理过期的缓存项（简单的清理策略）
    cleanup_expired_cache()

def cleanup_expired_cache():
    """清理过期的缓存项"""
    global grouping_cache

    # LRU缓存会自动清理过期条目，无需手动清理
    # 这里只记录一下缓存状态
    cache_stats = grouping_cache.stats()
    logging.debug(f"🧹 分组缓存状态: {cache_stats['size']}/{cache_stats['max_size']} 项")

# 📁 目录内容缓存管理函数
def get_cached_folder_content(folder_id_or_key):
    """获取缓存的目录内容"""
    # 支持直接传入缓存键或文件夹ID
    if isinstance(folder_id_or_key, str) and folder_id_or_key.startswith("folder_"):
        cache_key = folder_id_or_key
    else:
        cache_key = f"folder_{folder_id_or_key}"

    cached_data = folder_content_cache.get(cache_key)
    if cached_data is None:
        return None

    # LRU缓存已经处理了过期逻辑，直接返回内容
    logging.info(f"💾 命中目录缓存: {cache_key}")
    return cached_data.get('content')

def cache_folder_content(folder_id_or_key, content):
    """缓存目录内容"""
    # 支持直接传入缓存键或文件夹ID
    if isinstance(folder_id_or_key, str) and folder_id_or_key.startswith("folder_"):
        cache_key = folder_id_or_key
    else:
        cache_key = f"folder_{folder_id_or_key}"

    # 使用LRU缓存存储内容
    folder_content_cache.put(cache_key, {
        'timestamp': time.time(),
        'content': content
    })

    # 从content中获取项目数量（如果可能）
    item_count = "未知"
    if isinstance(content, dict):
        if 'files_and_folders' in content:
            item_count = len(content['files_and_folders'])
        elif 'folders' in content:
            item_count = len(content['folders'])

    logging.info(f"💾 缓存目录内容: {cache_key} ({item_count} 个项目)")

def cleanup_expired_folder_cache():
    """清理过期的目录缓存项"""
    # LRU缓存自动处理过期，这里只需要调用清理方法
    expired_count = folder_content_cache.cleanup_expired()
    if expired_count > 0:
        logging.info(f"🧹 清理了 {expired_count} 个过期目录缓存项")

def clear_folder_cache(folder_id=None):
    """清理指定文件夹的缓存，如果folder_id为None则清理所有缓存"""
    if folder_id is None:
        # 清理所有缓存
        count = folder_content_cache.size()
        folder_content_cache.clear()
        logging.info(f"🧹 清理了所有目录缓存 ({count} 个项目)")
    else:
        # 清理指定文件夹的缓存
        cache_key = f"folder_{folder_id}"
        folder_content_cache.delete(cache_key)
        logging.info(f"🧹 清理了文件夹 {folder_id} 的缓存")

        # 同时清理子文件夹的缓存（因为父文件夹变化可能影响子文件夹）
        # 注意：LRU缓存不支持直接遍历keys，这里需要重新设计
        # 暂时只清理直接缓存，子文件夹缓存会自然过期
        logging.info(f"🧹 已清理文件夹 {folder_id} 的直接缓存，相关子文件夹缓存将自然过期")

# 🚦 请求限流控制函数
def is_folder_request_rate_limited(folder_id):
    """检查文件夹是否被限流"""
    global folder_request_tracker

    current_time = time.time()
    folder_id_str = str(folder_id)

    # 清理过期的请求记录
    cleanup_expired_requests()

    # 检查该文件夹的请求历史
    if folder_id_str not in folder_request_tracker:
        folder_request_tracker[folder_id_str] = []

    folder_requests = folder_request_tracker[folder_id_str]

    # 过滤出时间窗口内的请求
    recent_requests = [
        req_time for req_time in folder_requests
        if current_time - req_time < FOLDER_REQUEST_LIMIT_DURATION
    ]

    # 更新请求列表
    folder_request_tracker[folder_id_str] = recent_requests

    # 检查是否超过限制
    if len(recent_requests) >= MAX_REQUESTS_PER_FOLDER:
        oldest_request = min(recent_requests)
        remaining_time = int(FOLDER_REQUEST_LIMIT_DURATION - (current_time - oldest_request))
        logging.warning(f"🚦 文件夹 {folder_id} 请求被限流，剩余等待时间: {remaining_time}秒")
        return True, remaining_time

    return False, 0

def record_folder_request(folder_id):
    """记录文件夹请求"""
    global folder_request_tracker

    current_time = time.time()
    folder_id_str = str(folder_id)

    if folder_id_str not in folder_request_tracker:
        folder_request_tracker[folder_id_str] = []

    folder_request_tracker[folder_id_str].append(current_time)
    logging.info(f"📝 记录文件夹 {folder_id} 的请求时间: {current_time}")

def cleanup_expired_requests():
    """清理过期的请求记录"""
    global folder_request_tracker

    current_time = time.time()
    expired_folders = []

    for folder_id, requests in folder_request_tracker.items():
        # 过滤出仍在时间窗口内的请求
        valid_requests = [
            req_time for req_time in requests
            if current_time - req_time < FOLDER_REQUEST_LIMIT_DURATION
        ]

        if valid_requests:
            folder_request_tracker[folder_id] = valid_requests
        else:
            expired_folders.append(folder_id)

    # 删除没有有效请求的文件夹记录
    for folder_id in expired_folders:
        del folder_request_tracker[folder_id]

    if expired_folders:
        logging.info(f"🧹 清理了 {len(expired_folders)} 个文件夹的过期请求记录")

def get_folder_grouping_analysis_internal(video_files, folder_id, log_func=None):
    """内部分组分析函数 - 优化版（带缓存）"""
    log_func = log_func or logging.info

    # 🔄 检查缓存
    cache_key = generate_cache_key(video_files, folder_id)
    cached_result = get_cached_grouping_result(cache_key)

    if cached_result is not None:
        log_func("⚡ 使用缓存的分组结果，跳过AI分析")
        return cached_result

    # 计算基本信息
    file_count = len(video_files)
    total_size_bytes = _calculate_total_size(video_files)
    size_str = _format_file_size(total_size_bytes)

    # 智能分组分析
    try:
        if video_files:
            log_func("🎯 开始智能文件分组分析")
            log_func(f"📊 总文件数量: {len(video_files)} 个")

            # 🚀 优化：直接按文件数量分批，而不是按子文件夹分组
            all_enhanced_groups = []

            # 使用配置的批处理大小
            log_func(f"📦 使用批处理大小: {CHUNK_SIZE} 个文件/批")

            # 🚀 简化策略：直接按文件数量分批处理
            if len(video_files) > CHUNK_SIZE:
                batches = split_files_into_batches(video_files, CHUNK_SIZE)
                log_func(f"📦 分批处理: {len(batches)} 批，减少API调用次数")

                for i, batch_files in enumerate(batches):
                    try:
                        check_task_cancelled()
                    except:
                        logging.warning("⚠️ 任务可能已被取消，但继续处理")

                    log_func(f"🔄 处理第 {i+1}/{len(batches)} 批: {len(batch_files)} 个文件")

                    # 添加超时保护
                    batch_start_time = time.time()
                    try:
                        batch_groups_result = process_files_for_grouping(batch_files, f"批次{i+1}")
                        batch_process_time = time.time() - batch_start_time

                        if batch_groups_result:
                            all_enhanced_groups.extend(batch_groups_result)
                            log_func(f"✅ 第 {i+1} 批处理完成: 生成 {len(batch_groups_result)} 个分组 (耗时: {batch_process_time:.1f}秒)")
                        else:
                            log_func(f"⏭️ 第 {i+1} 批未生成有效分组 (耗时: {batch_process_time:.1f}秒)")

                    except Exception as e:
                        batch_process_time = time.time() - batch_start_time
                        if "任务已被用户取消" in str(e):
                            log_func(f"⚠️ 任务已被用户取消，停止处理")
                            raise
                        log_func(f"❌ 第 {i+1} 批处理失败: {e} (耗时: {batch_process_time:.1f}秒)")
                        continue

                    # 更新进度
                    progress = 50.0 + ((i + 1) / len(batches)) * 30.0
                    log_func(f"🔄 智能分组进度: {progress:.3f}% - 🔄 处理第 {i+1}/{len(batches)} 批: {len(batch_files)} 个文件")
            else:
                # 单批处理
                log_func(f"📊 单批处理: {len(video_files)} 个文件")
                batch_start_time = time.time()
                try:
                    all_enhanced_groups = process_files_for_grouping(video_files, "全部文件")
                    batch_process_time = time.time() - batch_start_time
                    log_func(f"✅ 单批处理完成: 生成 {len(all_enhanced_groups) if all_enhanced_groups else 0} 个分组 (耗时: {batch_process_time:.1f}秒)")
                except Exception as e:
                    batch_process_time = time.time() - batch_start_time
                    if "任务已被用户取消" in str(e):
                        log_func(f"⚠️ 任务已被用户取消，停止处理")
                        raise
                    log_func(f"❌ 单批处理失败: {e} (耗时: {batch_process_time:.1f}秒)")
                    all_enhanced_groups = []

            # 🔄 第一步：合并相同名称的分组（解决批处理导致的重复分组）
            if len(all_enhanced_groups) > 1:
                log_func(f"🔄 开始合并相同名称的分组: {len(all_enhanced_groups)} 个分组")
                merge_start_time = time.time()
                try:
                    deduplicated_groups = merge_duplicate_named_groups(all_enhanced_groups)
                    merge_process_time = time.time() - merge_start_time

                    if len(deduplicated_groups) < len(all_enhanced_groups):
                        log_func(f"✅ 重复分组合并完成: {len(all_enhanced_groups)} → {len(deduplicated_groups)} 个分组 (耗时: {merge_process_time:.1f}秒)")
                    else:
                        log_func(f"⏭️ 无重复分组: 保持 {len(all_enhanced_groups)} 个分组 (耗时: {merge_process_time:.1f}秒)")

                    all_enhanced_groups = deduplicated_groups

                except Exception as e:
                    merge_process_time = time.time() - merge_start_time
                    log_func(f"❌ 重复分组合并失败: {e} (耗时: {merge_process_time:.1f}秒)")

            # 🔄 第二步：智能合并同系列分组（可选的AI合并）
            if len(all_enhanced_groups) > 1:
                log_func(f"🔄 开始智能合并: {len(all_enhanced_groups)} 个分组")
                merge_start_time = time.time()
                try:
                    merged_groups = merge_same_series_groups(all_enhanced_groups)
                    merge_process_time = time.time() - merge_start_time

                    if merged_groups and len(merged_groups) < len(all_enhanced_groups):
                        log_func(f"✅ 智能合并完成: {len(all_enhanced_groups)} → {len(merged_groups)} 个分组 (耗时: {merge_process_time:.1f}秒)")
                        movie_info = merged_groups
                    else:
                        log_func(f"⏭️ 无需合并: 保持 {len(all_enhanced_groups)} 个分组 (耗时: {merge_process_time:.1f}秒)")
                        movie_info = all_enhanced_groups

                except Exception as e:
                    merge_process_time = time.time() - merge_start_time
                    log_func(f"❌ 智能合并失败: {e} (耗时: {merge_process_time:.1f}秒)")
                    movie_info = all_enhanced_groups

                # 更新进度
                progress = 80.0 + 10.0
                log_func(f"🔄 智能分组进度: {progress:.3f}% - 🔄 智能合并完成")
            else:
                movie_info = all_enhanced_groups
                log_func(f"⏭️ 跳过合并: 只有 {len(all_enhanced_groups)} 个分组")

            log_func(f"🎯 分组分析完成: 输出 {len(movie_info)} 个分组")
        else:
            movie_info = []
    except Exception as e:
        log_func(f"⚠️ 生成分组信息时发生错误: {e}")
        movie_info = []

    # 构建返回结果
    result = {
        'success': True,
        'count': file_count,
        'size': size_str,
        'total_size_bytes': int(total_size_bytes),
        'movie_info': movie_info,
        'video_files': video_files
    }

    # 🔄 缓存结果（仅在有有效分组时缓存）
    if movie_info and len(movie_info) > 0:
        cache_grouping_result(cache_key, result)
        log_func(f"💾 分组结果已缓存，有效期: {GROUPING_CACHE_DURATION}秒")

    return result

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """清理缓存API"""
    try:
        cache_type = request.form.get('cache_type', 'all')
        folder_id = request.form.get('folder_id', None)

        if cache_type == 'folder' or cache_type == 'all':
            if folder_id:
                clear_folder_cache(int(folder_id))
                message = f"已清理文件夹 {folder_id} 的缓存"
            else:
                clear_folder_cache()
                message = "已清理所有目录缓存"

        if cache_type == 'grouping' or cache_type == 'all':
            global grouping_cache
            count = len(grouping_cache)
            grouping_cache.clear()
            message += f"，已清理 {count} 个分组缓存"

        if cache_type == 'scraping' or cache_type == 'all':
            global scraping_cache
            count = len(scraping_cache)
            scraping_cache.clear()
            message += f"，已清理 {count} 个刮削缓存"

        logging.info(f"🧹 缓存清理完成: {message}")
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        logging.error(f"清理缓存时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cache_status', methods=['GET'])
def cache_status():
    """获取缓存状态信息"""
    try:
        global folder_content_cache, grouping_cache, scraping_cache

        # 统计目录缓存
        folder_cache_stats = folder_content_cache.stats()
        folder_cache_count = folder_cache_stats['size']
        folder_cache_valid = folder_cache_count  # LRU缓存自动管理过期

        # 统计分组缓存
        grouping_cache_stats = grouping_cache.stats()
        grouping_cache_count = grouping_cache_stats['size']
        grouping_cache_valid = grouping_cache_count  # LRU缓存自动管理过期

        # 统计刮削缓存
        scraping_cache_stats = scraping_cache.stats()
        scraping_cache_count = scraping_cache_stats['size']
        scraping_cache_valid = scraping_cache_count  # LRU缓存自动管理过期

        return jsonify({
            'success': True,
            'cache_status': {
                'folder_cache': {
                    'total': folder_cache_count,
                    'valid': folder_cache_valid,
                    'expired': folder_cache_count - folder_cache_valid,
                    'duration': FOLDER_CONTENT_CACHE_DURATION
                },
                'grouping_cache': {
                    'total': grouping_cache_count,
                    'valid': grouping_cache_valid,
                    'expired': grouping_cache_count - grouping_cache_valid,
                    'duration': GROUPING_CACHE_DURATION
                },
                'scraping_cache': {
                    'total': scraping_cache_count,
                    'valid': scraping_cache_valid,
                    'expired': scraping_cache_count - scraping_cache_valid,
                    'duration': SCRAPING_CACHE_DURATION
                }
            }
        })

    except Exception as e:
        logging.error(f"获取缓存状态时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cancel_task', methods=['POST'])
def cancel_task():
    """取消当前正在运行的任务"""
    try:
        cancel_current_task()
        return jsonify({'success': True, 'message': '任务取消请求已发送'})
    except Exception as e:
        logging.error(f"取消任务时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/performance_stats', methods=['GET'])
def get_performance_stats():
    """获取性能统计信息"""
    try:
        stats = {
            'app_state': app_state.get_stats(),
            'performance': performance_monitor.get_stats(),
            'system_info': {
                'python_version': sys.version,
                'platform': sys.platform,
                'current_time': datetime.datetime.now().isoformat()
            }
        }
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logging.error(f"获取性能统计时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/reset_performance_stats', methods=['POST'])
def reset_performance_stats():
    """重置性能统计"""
    try:
        performance_monitor.reset_stats()
        return jsonify({'success': True, 'message': '性能统计已重置'})
    except Exception as e:
        logging.error(f"重置性能统计时发生错误: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/get_file_list', methods=['POST'])
def get_file_list():
    """获取指定文件夹下的视频文件列表（递归）"""
    try:
        folder_id = request.form.get('folder_id', '0')
        folder_id = int(folder_id)

        logging.info(f"获取文件夹 {folder_id} 下的视频文件列表")

        file_list = []
        get_video_files_recursively(folder_id, file_list)

        # 转换为前端需要的格式
        formatted_files = []
        for file_item in file_list:
            formatted_files.append({
                'parentFileId': file_item['parentFileId'],
                'fileId': file_item['fileId'],
                'filename': os.path.basename(file_item['file_path']),  # 只保留文件名
                'file_name': file_item['file_path'],  # 完整路径
                'size': file_item['size_gb'],
            })

        logging.info(f"找到 {len(formatted_files)} 个视频文件")
        return jsonify({
            'success': True,
            'files': formatted_files,
            'total_count': len(formatted_files)
        })

    except Exception as e:
        logging.error(f"获取文件列表时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/scrape_preview', methods=['POST'])
def scrape_preview():
    """刮削预览"""
    try:
        # 开始新任务
        start_new_task(f"scrape_preview_{int(time.time())}")

        selected_files_json = request.form.get('files')
        if not selected_files_json:
            return jsonify({'success': False, 'error': '没有选择任何项目进行刮削。'})

        selected_items = json.loads(selected_files_json)
        logging.info(f"🎬 开始刮削预览，选择进行刮削的项目数量: {len(selected_items)}")

        # 检查任务是否被取消
        check_task_cancelled()

        # 收集所有需要处理的文件
        all_files = []

        # 添加详细的调试信息
        logging.info(f"前端传递的完整数据: {json.dumps(selected_items, indent=2, ensure_ascii=False)}")

        # 前端应该已经传递了 file_name 字段，如果没有则记录警告
        for item in selected_items:
            if not item.get('file_name'):
                logging.warning(f"项目缺少 file_name 字段: {item.get('fileId')} - {item.get('name')}")

        for i, item in enumerate(selected_items):
            # 检查任务是否被取消
            check_task_cancelled()

            logging.info(f"调试 - 处理第 {i+1} 个项目: {item}")
            logging.info(f"调试 - 项目字段: name={item.get('name')}, file_name={item.get('file_name')}")

            if item.get('is_dir'):
                # 如果是文件夹，递归获取其中的视频文件
                folder_id = item.get('fileId')
                folder_name = item.get('name') or item.get('filename') or item.get('file_name', 'Unknown')
                # 获取文件夹的完整路径
                folder_path = item.get('file_name', '')
                logging.info(f"📂 处理文件夹: {folder_name} (ID: {folder_id})")
                logging.info(f"📂 文件夹路径: {folder_path}")
                folder_files = []
                try:
                    # 传递正确的文件夹路径
                    get_video_files_recursively(int(folder_id), folder_files, folder_path)
                    logging.info(f"📂 文件夹 {folder_name} 中找到 {len(folder_files)} 个视频文件")
                    all_files.extend(folder_files)
                except Exception as e:
                    if "任务已被用户取消" in str(e):
                        logging.info("🛑 文件夹遍历过程中任务被用户取消")
                        raise
                    else:
                        logging.error(f"递归获取文件夹 {folder_name} 中的视频文件时发生错误: {e}")
                        continue
            else:
                # 如果是文件，直接添加
                logging.info(f"处理文件: {item}")
                # 优先使用 file_name（完整路径），然后使用 name（文件名）
                filename = item.get('file_name') or item.get('name')
                if filename:
                    _, ext = os.path.splitext(filename)
                    logging.info(f"文件名: {filename}, 扩展名: {ext}, 是否为视频: {ext.lower()[1:] in SUPPORTED_MEDIA_TYPES}")
                    if ext.lower()[1:] in SUPPORTED_MEDIA_TYPES:
                        # 创建文件项对象，保持与 recursive_list_video_files 一致的格式
                        file_item = {
                            'parentFileId': item.get('parentFileId'),
                            'fileId': item.get('fileId'),
                            'filename': os.path.basename(filename),
                            'file_path': filename,
                            'size_gb': item.get('size', ''),
                            'type': 0  # 文件类型
                        }
                        all_files.append(file_item)
                        logging.info(f"添加文件到处理列表: {filename}")
                    else:
                        logging.info(f"跳过非视频文件: {filename}")
                else:
                    logging.warning(f"文件缺少 name 和 file_name 字段: {item}")

        logging.info(f"总共收集到 {len(all_files)} 个视频文件")
        logging.info(f"需要刮削的文件 {all_files}")

        # 🔍 优化文件过滤逻辑，提前识别不需要处理的文件
        files_to_scrape = []
        already_processed = 0

        for file_item in all_files:
            filename = file_item['file_path']
            # 更精确的检查文件名是否已包含TMDB信息
            has_tmdb = 'tmdb-' in filename.lower()
            has_size_info = any(size_marker in filename for size_marker in ['GB', 'MB', 'TB'])

            # 如果文件名已经包含TMDB信息和大小信息，跳过处理
            if has_tmdb and has_size_info:
                already_processed += 1
                logging.debug(f"⏭️ 跳过已处理文件: {filename}")
            else:
                files_to_scrape.append(file_item)

        if already_processed > 0:
            logging.info(f"⏭️ 跳过 {already_processed} 个已处理的文件")

        if not files_to_scrape:
            logging.info("✅ 所有文件都已处理过，无需刮削")
            return jsonify({'success': True, 'results': [], 'message': '所有文件都已处理过'})

        logging.info(f"🎯 需要刮削的文件数量: {len(files_to_scrape)} (总文件: {len(all_files)}, 已处理: {already_processed})")

        # 检查任务是否被取消
        check_task_cancelled()

        # 🚀 优化分块处理策略
        chunks = [files_to_scrape[i:i + CHUNK_SIZE] for i in range(0, len(files_to_scrape), CHUNK_SIZE)]
        all_scraped_results = []

        logging.info(f"📦 分为 {len(chunks)} 个批次处理 (每批次 {CHUNK_SIZE} 个文件)")
        logging.info(f"🔧 性能配置: QPS_LIMIT={QPS_LIMIT}, MAX_WORKERS={MAX_WORKERS}")

        # 记录开始时间用于性能分析
        start_time = time.time()
        completed_batches = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            future_info = {}  # 存储 future 对象的额外信息

            for i, chunk in enumerate(chunks):

                # 检查任务是否被取消
                check_task_cancelled()

                logging.info(f"🚀 提交第 {i+1}/{len(chunks)} 个批次进行处理 (包含 {len(chunk)} 个文件)")
                future = executor.submit(extract_movie_name_and_info, chunk)
                futures.append(future)
                future_info[future] = {'batch_num': i+1, 'batch_size': len(chunk)}

            for future in as_completed(futures):
                batch_num = future_info[future]['batch_num']
                batch_size = future_info[future]['batch_size']
                try:
                    # 检查任务是否被取消
                    check_task_cancelled()

                    batch_start_time = time.time()
                    results = future.result()
                    batch_end_time = time.time()
                    batch_duration = batch_end_time - batch_start_time

                    completed_batches += 1

                    if results:
                        all_scraped_results.extend(results)
                        logging.info(f"✅ 完成第 {batch_num} 个批次 ({batch_size} 个文件)，获得 {len(results)} 个结果，耗时 {batch_duration:.2f}秒")
                    else:
                        logging.info(f"⚠️ 第 {batch_num} 个批次未获得结果，耗时 {batch_duration:.2f}秒")

                    # 计算整体进度
                    progress = (completed_batches / len(chunks)) * 100
                    elapsed_time = time.time() - start_time
                    avg_time_per_batch = elapsed_time / completed_batches
                    estimated_remaining = (len(chunks) - completed_batches) * avg_time_per_batch

                    logging.info(f"📊 进度: {completed_batches}/{len(chunks)} ({progress:.1f}%), 预计剩余时间: {estimated_remaining:.1f}秒")

                except Exception as exc:
                    if "任务已被用户取消" in str(exc):
                        logging.info("🛑 刮削任务被用户取消")
                        raise
                    else:
                        logging.error(f'第 {batch_num} 个批次处理异常: {exc}', exc_info=True)

        logging.info(f"🎉 刮削预览完成。总结果: {len(all_scraped_results)}")
        return jsonify({'success': True, 'results': all_scraped_results})

    except Exception as e:
        if "任务已被用户取消" in str(e):
            logging.info("🛑 刮削预览任务被用户取消")
            return jsonify({'success': False, 'error': '任务已被用户取消', 'cancelled': True})
        else:
            logging.error(f"刮削预览期间发生错误: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)})

@app.route('/apply_rename', methods=['POST'])
def apply_rename():
    """应用重命名 - 支持批量重命名，参考movie115实现"""
    try:
        rename_data_json = request.form.get('rename_data')
        if not rename_data_json:
            logging.warning("没有提供重命名数据。")
            return jsonify({'success': False, 'error': '没有提供重命名数据。'})

        rename_data = json.loads(rename_data_json)
        logging.info(f"📋 rename_data: {rename_data}")
        if not rename_data:
            logging.warning("没有文件需要重命名。")
            return jsonify({'success': False, 'error': '没有文件需要重命名。'})

        # 构建重命名字典和原始名称映射
        namedict = {}
        original_names_map = {}  # 用于存储原始名称，以便在结果中显示
        for item in rename_data:
            item_id = item.get('fileId') or item.get('id')
            item_type = item.get('type', 'file')
            new_name = item.get('suggested_name') or item.get('new_name')
            original_name = item.get('filename') or item.get('original_name') or item.get('name')

            if item_type == 'file' and item_id and new_name:
                namedict[item_id] = new_name
                original_names_map[item_id] = original_name
                logging.info(f"📝 准备重命名文件 ID: {item_id}, 原始名称: {original_name}, 新名称: {new_name}")

        if not namedict:
            logging.warning("没有文件需要重命名。")
            return jsonify({'success': False, 'error': '没有文件需要重命名。'})

        # 在执行重命名之前，将重命名数据保存到文件，方便恢复
        backup_data = {
            'namedict': namedict,
            'original_names_map': original_names_map
        }
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file_path = f'rename_data_backup_{timestamp}.json'
        try:
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=4)
            logging.info(f"💾 重命名数据已成功备份到 {backup_file_path}")
        except Exception as e:
            logging.error(f"备份重命名数据时发生错误: {e}", exc_info=True)
            # 不中断流程，继续尝试重命名

        # 将 namedict 拆分成多组，每组 200 个（参考movie115的批次大小）
        chunk_size = 30
        namedict_chunks = [dict(list(namedict.items())[i:i + chunk_size]) for i in range(0, len(namedict), chunk_size)]

        all_results = []
        overall_success = True
        overall_error = []

        for i, chunk in enumerate(namedict_chunks):
            logging.info(f"🔄 开始处理第 {i+1}/{len(namedict_chunks)} 批重命名，包含 {len(chunk)} 个文件。")

            try:
                # 执行当前批次的重命名，使用批量QPS限制（1 QPS）
                rename_result = rename(chunk, use_batch_qps=True)

                # 处理API返回结果：当API返回code=0时，data可能为null，这表示成功
                # rename函数返回validate_api_response的结果，成功时可能返回None
                if rename_result is None:
                    # API返回成功（code=0, data=null）
                    logging.info(f"✅ 第 {i+1} 批重命名成功，API返回成功状态")
                    for item_id, new_name in chunk.items():
                        all_results.append({
                            'id': item_id,
                            'type': 'file',
                            'original_name': original_names_map.get(item_id, '未知'),
                            'new_name': new_name,
                            'status': 'success'
                        })
                elif isinstance(rename_result, dict) and rename_result.get('success', True):
                    # 如果返回字典且success为True
                    logging.info(f"✅ 第 {i+1} 批重命名成功，结果: {rename_result}")
                    for item_id, new_name in chunk.items():
                        all_results.append({
                            'id': item_id,
                            'type': 'file',
                            'original_name': original_names_map.get(item_id, '未知'),
                            'new_name': new_name,
                            'status': 'success'
                        })
                else:
                    # 处理失败情况
                    overall_success = False
                    if isinstance(rename_result, dict):
                        error_message = rename_result.get('error', '批量重命名未知错误')
                        details = rename_result.get('result')
                    else:
                        error_message = f'重命名返回异常结果: {rename_result}'
                        details = None

                    logging.error(f"❌ 第 {i+1} 批批量重命名失败: {error_message}, 详情: {details}")
                    overall_error.append(f"第 {i+1} 批失败: {error_message} (详情: {details})")
                    # 对于失败的批次，将该批次中的文件标记为失败
                    for item_id, new_name in chunk.items():
                        all_results.append({
                            'id': item_id,
                            'type': 'file',
                            'original_name': original_names_map.get(item_id, '未知'),
                            'new_name': new_name,
                            'status': 'failed',
                            'error': error_message
                        })

            except AccessTokenError as e:
                overall_success = False
                error_message = f'Access Token错误: {str(e)}'
                logging.error(f"❌ 第 {i+1} 批 Access Token错误: {e}")
                overall_error.append(f"第 {i+1} 批失败: {error_message}")
                # 记录失败的重命名
                for item_id, new_name in chunk.items():
                    all_results.append({
                        'id': item_id,
                        'type': 'file',
                        'original_name': original_names_map.get(item_id, '未知'),
                        'new_name': new_name,
                        'status': 'failed',
                        'error': error_message
                    })

            except requests.HTTPError as e:
                overall_success = False
                error_message = f'HTTP错误: {str(e)}'
                logging.error(f"❌ 第 {i+1} 批 HTTP错误: {e}")
                overall_error.append(f"第 {i+1} 批失败: {error_message}")
                # 记录失败的重命名
                for item_id, new_name in chunk.items():
                    all_results.append({
                        'id': item_id,
                        'type': 'file',
                        'original_name': original_names_map.get(item_id, '未知'),
                        'new_name': new_name,
                        'status': 'failed',
                        'error': error_message
                    })

            except Exception as e:
                overall_success = False
                error_message = str(e)
                logging.error(f"❌ 第 {i+1} 批重命名发生未知错误: {e}", exc_info=True)
                overall_error.append(f"第 {i+1} 批失败: {error_message}")
                # 记录失败的重命名
                for item_id, new_name in chunk.items():
                    all_results.append({
                        'id': item_id,
                        'type': 'file',
                        'original_name': original_names_map.get(item_id, '未知'),
                        'new_name': new_name,
                        'status': 'failed',
                        'error': error_message
                    })

        # 重命名操作完成后，清理相关缓存
        if overall_success or any(result.get('status') == 'success' for result in all_results):
            # 如果有任何文件重命名成功，清理相关缓存
            logging.info("🧹 重命名操作完成，开始清理相关缓存...")

            # 清理刮削缓存（因为文件名已改变，旧的刮削结果不再有效）
            old_scraping_size = scraping_cache.size()
            scraping_cache.clear()
            logging.info(f"🧹 清理刮削缓存: {old_scraping_size} 项")

            # 清理分组缓存（因为文件名已改变，分组结果可能不再准确）
            old_grouping_size = grouping_cache.size()
            grouping_cache.clear()
            logging.info(f"🧹 清理分组缓存: {old_grouping_size} 项")

            # 清理文件夹内容缓存（因为文件名已改变，需要刷新文件列表）
            old_folder_size = folder_content_cache.size()
            folder_content_cache.clear()
            logging.info(f"🧹 清理文件夹内容缓存: {old_folder_size} 项")

            # 清理路径缓存（如果重命名的是文件夹，路径信息需要更新）
            # 这里保守一些，只在缓存过多时清理，避免影响性能
            if folder_path_cache.size() > 200:
                old_path_size = folder_path_cache.size()
                folder_path_cache.clear()
                logging.info(f"🧹 清理路径缓存: {old_path_size} 项")

            total_cleared = old_scraping_size + old_grouping_size + old_folder_size
            logging.info(f"🧹 重命名后缓存清理完成，共清理 {total_cleared} 项缓存")

        # 参考movie115的返回格式
        if overall_success:
            logging.info(f"🎉 批量重命名完成: 全部成功，共处理 {len(all_results)} 个文件")
            return jsonify({'success': True, 'results': all_results})
        else:
            logging.info(f"⚠️ 批量重命名完成: 部分或全部失败，详情: {overall_error}")
            return jsonify({
                'success': False,
                'error': '部分或全部批量重命名失败。',
                'details': overall_error,
                'results': all_results
            })

    except Exception as e:
        logging.error(f"应用重命名时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/move_files_direct', methods=['POST'])
def move_files_direct():
    """直接移动选中的文件到指定文件夹"""
    try:
        move_data_json = request.form.get('move_data')
        target_folder_id = request.form.get('target_folder_id')

        if not move_data_json:
            return jsonify({'success': False, 'error': '没有提供移动数据。'})

        if not target_folder_id:
            return jsonify({'success': False, 'error': '没有提供目标文件夹ID。'})

        try:
            target_folder_id = int(target_folder_id)
        except ValueError:
            return jsonify({'success': False, 'error': '目标文件夹ID必须是数字。'})

        move_data = json.loads(move_data_json)
        if not move_data:
            return jsonify({'success': False, 'error': '没有文件需要移动。'})

        # 提取文件ID列表
        file_ids = []
        for item in move_data:
            file_id = item.get('fileId')
            if file_id:
                try:
                    file_ids.append(int(file_id))
                except ValueError:
                    logging.warning(f"无效的文件ID: {file_id}")
                    continue

        if not file_ids:
            return jsonify({'success': False, 'error': '没有有效的文件ID。'})

        logging.info(f"📦 准备移动 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
        logging.info(f"📋 文件ID列表: {file_ids}")

        # 调用移动API
        result = move(file_ids, target_folder_id)

        if result.get("success"):
            logging.info(f"✅ 成功移动 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
            return jsonify({
                'success': True,
                'message': f'成功移动 {len(file_ids)} 个文件到目标文件夹。',
                'moved_count': len(file_ids),
                'target_folder_id': target_folder_id
            })
        else:
            error_message = result.get("message", "移动文件失败，请检查目标文件夹ID是否正确。")
            logging.error(f"移动文件失败: {error_message}")
            return jsonify({'success': False, 'error': error_message})

    except json.JSONDecodeError as e:
        logging.error(f"解析移动数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': '移动数据格式错误。'})
    except Exception as e:
        logging.error(f"直接移动文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/rename_files', methods=['POST'])
def rename_files():
    """重命名选中的文件"""
    try:
        rename_data_json = request.form.get('rename_data')
        if not rename_data_json:
            return jsonify({'success': False, 'error': '没有提供重命名数据。'})

        rename_data = json.loads(rename_data_json)
        if not rename_data:
            return jsonify({'success': False, 'error': '没有文件需要重命名。'})

        logging.info(f"准备重命名 {len(rename_data)} 个文件")

        # 构建重命名字典
        rename_dict = {}
        for item in rename_data:
            file_id = item.get('fileId')
            # 支持多种格式：newName（普通重命名）、suggested_name（刮削预览重命名）、new_name（智能重命名）
            new_name = item.get('newName') or item.get('suggested_name') or item.get('new_name')
            if file_id and new_name:
                rename_dict[file_id] = new_name

        if not rename_dict:
            return jsonify({'success': False, 'error': '没有有效的重命名数据。'})

        # 分批处理重命名，每批最多30个文件
        BATCH_SIZE = 30
        file_items = list(rename_dict.items())
        total_files = len(file_items)
        batches = [file_items[i:i + BATCH_SIZE] for i in range(0, total_files, BATCH_SIZE)]

        logging.info(f"总共 {total_files} 个文件，分为 {len(batches)} 批处理，每批最多 {BATCH_SIZE} 个文件")

        successful_renames = []
        failed_renames = []

        for batch_index, batch in enumerate(batches):
            batch_dict = dict(batch)
            batch_size = len(batch_dict)

            logging.info(f"处理第 {batch_index + 1}/{len(batches)} 批，包含 {batch_size} 个文件")

            try:
                # 执行当前批次的重命名，使用批量QPS限制（1 QPS）
                result = rename(batch_dict, use_batch_qps=True)
                logging.info(f"第 {batch_index + 1} 批重命名成功，结果: {result}")

                # 记录成功的重命名
                for file_id, new_name in batch_dict.items():
                    successful_renames.append({
                        'fileId': file_id,
                        'newName': new_name,
                        'status': 'success'
                    })

            except Exception as e:
                logging.error(f"第 {batch_index + 1} 批重命名发生错误: {e}", exc_info=True)
                # 记录失败的重命名
                for file_id, new_name in batch_dict.items():
                    failed_renames.append({
                        'fileId': file_id,
                        'newName': new_name,
                        'status': 'failed',
                        'error': str(e)
                    })

        # 汇总结果
        total_successful = len(successful_renames)
        total_failed = len(failed_renames)

        logging.info(f"批量重命名完成: 成功 {total_successful} 个，失败 {total_failed} 个")

        # 构建详细结果数组，包含原始文件名信息
        all_results = []

        # 添加成功的结果
        for success_item in successful_renames:
            # 从原始重命名数据中找到对应的原始文件名
            original_name = "未知"
            for orig_item in rename_data:
                if str(orig_item.get('fileId')) == str(success_item['fileId']):
                    original_name = orig_item.get('original_name', orig_item.get('newName', '未知'))
                    break

            all_results.append({
                'status': 'success',
                'original_name': original_name,
                'new_name': success_item['newName'],
                'error': ''
            })

        # 添加失败的结果
        for failed_item in failed_renames:
            # 从原始重命名数据中找到对应的原始文件名
            original_name = "未知"
            for orig_item in rename_data:
                if str(orig_item.get('fileId')) == str(failed_item['fileId']):
                    original_name = orig_item.get('original_name', orig_item.get('newName', '未知'))
                    break

            all_results.append({
                'status': 'failed',
                'original_name': original_name,
                'new_name': failed_item['newName'],
                'error': failed_item.get('error', '未知错误')
            })

        # 如果有任何文件重命名成功，清理相关缓存
        if total_successful > 0:
            logging.info("🧹 重命名操作完成，开始清理相关缓存...")

            # 清理刮削缓存（因为文件名已改变，旧的刮削结果不再有效）
            old_scraping_size = scraping_cache.size()
            scraping_cache.clear()
            logging.info(f"🧹 清理刮削缓存: {old_scraping_size} 项")

            # 清理分组缓存（因为文件名已改变，分组结果可能不再准确）
            old_grouping_size = grouping_cache.size()
            grouping_cache.clear()
            logging.info(f"🧹 清理分组缓存: {old_grouping_size} 项")

            # 清理文件夹内容缓存（因为文件名已改变，需要刷新文件列表）
            old_folder_size = folder_content_cache.size()
            folder_content_cache.clear()
            logging.info(f"🧹 清理文件夹内容缓存: {old_folder_size} 项")

            total_cleared = old_scraping_size + old_grouping_size + old_folder_size
            logging.info(f"🧹 重命名后缓存清理完成，共清理 {total_cleared} 项缓存")

        if total_failed == 0:
            return jsonify({
                'success': True,
                'message': f'批量重命名成功，共处理 {total_successful} 个文件',
                'successful_count': total_successful,
                'failed_count': total_failed,
                'results': all_results
            })
        elif total_successful == 0:
            return jsonify({
                'success': False,
                'error': f'批量重命名全部失败，共 {total_failed} 个文件失败',
                'successful_count': total_successful,
                'failed_count': total_failed,
                'results': all_results
            })
        else:
            return jsonify({
                'success': True,
                'message': f'批量重命名部分成功: 成功 {total_successful} 个，失败 {total_failed} 个',
                'successful_count': total_successful,
                'failed_count': total_failed,
                'results': all_results
            })

    except json.JSONDecodeError as e:
        logging.error(f"解析重命名数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': '重命名数据格式错误。'})
    except Exception as e:
        logging.error(f"重命名文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_files', methods=['POST'])
def delete_files():
    """删除选中的文件"""
    try:
        delete_data_json = request.form.get('delete_data')
        if not delete_data_json:
            return jsonify({'success': False, 'error': '没有提供删除数据。'})

        delete_data = json.loads(delete_data_json)
        if not delete_data:
            return jsonify({'success': False, 'error': '没有文件需要删除。'})

        logging.info(f"准备删除 {len(delete_data)} 个文件")

        # 收集文件ID
        file_ids = []
        for item in delete_data:
            file_id = item.get('fileId')
            if file_id:
                file_ids.append(file_id)

        if not file_ids:
            return jsonify({'success': False, 'error': '没有有效的文件ID。'})

        # 分批处理删除，每批最多100个文件
        BATCH_SIZE = 100
        total_files = len(file_ids)
        batches = [file_ids[i:i + BATCH_SIZE] for i in range(0, total_files, BATCH_SIZE)]

        logging.info(f"总共 {total_files} 个文件，分为 {len(batches)} 批处理，每批最多 {BATCH_SIZE} 个文件")

        successful_deletes = 0
        failed_deletes = 0

        for batch_index, batch in enumerate(batches):
            batch_size = len(batch)
            logging.info(f"处理第 {batch_index + 1}/{len(batches)} 批，包含 {batch_size} 个文件")

            try:
                # 执行当前批次的删除
                result = delete(batch)
                logging.info(f"第 {batch_index + 1} 批删除成功，结果: {result}")
                successful_deletes += batch_size

            except Exception as e:
                logging.error(f"第 {batch_index + 1} 批删除发生错误: {e}", exc_info=True)
                failed_deletes += batch_size

        logging.info(f"批量删除完成: 成功 {successful_deletes} 个，失败 {failed_deletes} 个")

        if failed_deletes == 0:
            return jsonify({
                'success': True,
                'message': f'批量删除成功，共删除 {successful_deletes} 个文件',
                'successful_count': successful_deletes,
                'failed_count': failed_deletes
            })
        elif successful_deletes == 0:
            return jsonify({
                'success': False,
                'error': f'批量删除全部失败，共 {failed_deletes} 个文件失败',
                'successful_count': successful_deletes,
                'failed_count': failed_deletes
            })
        else:
            return jsonify({
                'success': True,
                'message': f'批量删除部分成功: 成功 {successful_deletes} 个，失败 {failed_deletes} 个',
                'successful_count': successful_deletes,
                'failed_count': failed_deletes
            })

    except json.JSONDecodeError as e:
        logging.error(f"解析删除数据JSON时发生错误: {e}")
        return jsonify({'success': False, 'error': '删除数据格式错误。'})
    except Exception as e:
        logging.error(f"删除文件时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

# ================================
# 智能文件夹命名相关函数
# ================================

def validate_folder_id_for_naming(folder_id_str):
    """验证文件夹ID的有效性"""
    if not folder_id_str or folder_id_str == 'null' or folder_id_str == 'undefined':
        return None, '无效的文件夹ID'

    try:
        folder_id = int(folder_id_str)
        return folder_id, None
    except (ValueError, TypeError):
        return None, '文件夹ID必须是数字'


def get_sampled_video_files(folder_id, max_files=50):
    """获取文件夹中的视频文件，如果数量过多则进行采样"""
    video_files = []

    try:
        # 为智能重命名功能使用优化的扫描策略
        get_video_files_for_naming(folder_id, video_files)
    except Exception as e:
        if "任务已被用户取消" in str(e):
            raise TaskCancelledException("文件遍历过程中任务被用户取消")
        else:
            raise FileSystemError(f"获取文件列表失败: {str(e)}")

    if not video_files:
        raise ValidationError('文件夹中没有找到视频文件')

    # 如果文件数量超过限制，随机取样
    if len(video_files) > max_files:
        import random
        sampled_video_files = random.sample(video_files, max_files)
        logging.info(f"📊 文件数量 {len(video_files)} 超过{max_files}个，随机取样 {max_files} 个文件进行AI分析")
    else:
        sampled_video_files = video_files
        logging.info(f"📊 文件数量 {len(video_files)} 在限制内，使用全部文件进行AI分析")

    return video_files, sampled_video_files


def get_folder_naming_prompt():
    """获取文件夹命名的AI提示词"""
    return """
你是一个专业的媒体文件夹命名助手。基于以下视频文件列表，为包含这些文件的文件夹建议一个合适且一致的名称。

**🚨 重要提醒：**
- 文件夹名称总长度必须严格控制在30个字符以内
- 对于混合内容，绝对不能列出所有作品名称，必须使用简洁的描述性名称
- 只返回一个最佳建议，不要提供多个选项

**核心命名规则：**

**电影命名规则：**
1. 单部电影：`电影名 (年份)`
   - 示例：`复仇者联盟 (2012)` (11字符)
   - 示例：`肖申克的救赎 (1994)` (13字符)

2. 电影系列/合集：
   - 2-3部作品：`电影名系列 (年份范围)`
   - 示例：`复仇者联盟系列 (2012-2019)` (17字符)
   - 4部以上：`电影名 系列合集`
   - 示例：`速度与激情 系列合集` (10字符)

**电视剧命名规则：**
1. 单季电视剧：`剧名 (年份) S01`
   - 示例：`权力的游戏 (2011) S01` (14字符)
   - 示例：`老友记 (1994) S01` (12字符)

2. 多季电视剧：
   - 2-4季：`剧名 (年份) S01-S04`
   - 示例：`绝命毒师 (2008) S01-S05` (16字符)
   - 5季以上：`剧名 完整系列`
   - 示例：`老友记 完整系列` (8字符)

**混合内容命名规则（重要）：**
当文件夹包含多个不同IP的内容时，必须使用简洁的描述性名称：

1. **多个电视剧系列**：
   - `电视剧合集` (5字符)
   - `剧集收藏` (4字符)
   - `经典剧集` (4字符)

2. **多个电影**：
   - `电影合集` (4字符)
   - `影片收藏` (4字符)
   - `经典电影` (4字符)

3. **按年代分类**：
   - `2020年代剧集` (7字符)
   - `经典老片` (4字符)

4. **按类型分类**：
   - `动作片合集` (5字符)
   - `科幻剧集` (4字符)

**❌ 错误示例（绝对不要这样做）：**
- `剧名1 (年份) S01, 剧名2 (年份) S01, 剧名3 (年份) S01` (太长，超过30字符)
- `电影1 (年份), 电影2 (年份), 电影3 (年份)` (太长，列出所有名称)

**✅ 正确示例：**
- `电视剧合集` (简洁描述性名称)
- `经典剧集` (按特征分类)
- `2020年代剧集` (按年代分类)

**一致性保证机制：**
1. **长度控制**：总长度严格不超过30个字符
2. **格式统一**：严格按照模板格式
3. **避免特殊字符**：不使用 / \\ : * ? " < > |
4. **简洁原则**：混合内容必须使用描述性名称

**分析步骤：**
1. 统计文件中的不同IP数量
2. **关键判断**：
   - 如果是单一IP：使用对应的电影/电视剧规则
   - **如果是多个不同IP：必须使用混合内容的描述性名称规则，绝对不能列出所有作品名称**
3. 检查名称长度是否在30字符以内
4. 确保格式符合规范

**🚨 特别强调（混合内容处理）：**
- 当文件夹包含2个或以上不同IP的内容时，必须使用简洁的描述性名称
- 绝对不能使用"作品1, 作品2, 作品3"的格式
- 必须使用"电视剧合集"、"剧集收藏"、"经典剧集"等描述性名称
- 不要返回数组或多个建议，只返回一个最佳的描述性名称

**输出要求：**
只返回一个JSON对象，包含最佳建议：
{
    "suggested_name": "建议的文件夹名称（30字符以内）",
    "media_type": "movie/tv/mixed",
    "title_source": "中文官方译名/中文通用译名/描述性名称",
    "year_range": "年份或年份范围",
    "content_count": "作品数量统计",
    "reasoning": "命名理由（说明为什么选择这个名称，字符数统计）"
}

文件列表：
"""


def generate_folder_name_with_ai(file_list):
    """使用AI生成文件夹名称建议"""
    user_input_content = repr(file_list)
    folder_name_prompt = get_folder_naming_prompt()

    max_retries = AI_MAX_RETRIES
    retry_delay = AI_RETRY_DELAY
    suggested_name = None

    # 构建完整的提示词
    full_prompt = f"{folder_name_prompt}\n\n{user_input_content}"

    for attempt in range(max_retries):
        try:
            # 检查任务是否被取消
            check_task_cancelled()

            # 使用统一的AI API调用函数
            ai_content = call_ai_api(full_prompt, GROUPING_MODEL)

            if not ai_content:
                logging.warning(f"AI API调用返回空结果 (尝试 {attempt + 1}/{max_retries})")
                continue

            logging.info(f"AI原始响应: {ai_content}")

            # 解析AI响应
            suggested_name = parse_folder_name_from_ai_response(ai_content)

            if suggested_name:
                break

        except Exception as e:
            logging.error(f"AI请求处理失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise AIServiceError(f'AI服务请求失败: {str(e)}')

    if not suggested_name:
        raise AIServiceError('AI未能生成有效的文件夹名称建议')

    return suggested_name


def parse_folder_name_from_ai_response(ai_content):
    """从AI响应中解析文件夹名称"""
    # 首先尝试解析JSON格式
    json_data = parse_json_from_ai_response(ai_content)

    if json_data:
        if isinstance(json_data, dict) and 'suggested_name' in json_data:
            suggested_name = json_data['suggested_name']
            media_type = json_data.get('media_type', '')
            reasoning = json_data.get('reasoning', '')
            logging.info(f"🎯 成功解析JSON格式的建议名称: {suggested_name}")
            logging.info(f"📊 媒体类型: {media_type}, 命名理由: {reasoning}")
            return suggested_name
        elif isinstance(json_data, list) and len(json_data) > 0:
            first_item = json_data[0]
            if isinstance(first_item, dict) and 'suggested_name' in first_item:
                suggested_name = first_item['suggested_name']
                media_type = first_item.get('media_type', '')
                reasoning = first_item.get('reasoning', '')
                logging.info(f"🎯 成功解析JSON数组格式的建议名称: {suggested_name}")
                logging.info(f"📊 媒体类型: {media_type}, 命名理由: {reasoning}")
                return suggested_name

    # 如果JSON解析失败，尝试直接使用响应内容
    logging.warning(f"JSON解析失败，尝试使用原始内容")

    # 清理响应内容，移除可能的格式化字符
    clean_content = ai_content.strip()
    clean_content = re.sub(r'```json|```', '', clean_content)
    clean_content = re.sub(r'[{}"\[\]]', '', clean_content)
    clean_content = re.sub(r'suggested_name\s*:\s*', '', clean_content)
    clean_content = clean_content.strip()

    if clean_content and len(clean_content) <= 100:  # 合理的文件夹名称长度
        return clean_content

    return None


def clean_suggested_folder_name(suggested_name):
    """清理和验证建议的文件夹名称"""
    if not suggested_name or not isinstance(suggested_name, str):
        return None

    # 清理建议的名称
    suggested_name = suggested_name.strip().strip('"\'')

    # 移除可能的非法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        suggested_name = suggested_name.replace(char, '')

    # 限制长度
    if len(suggested_name) > 50:
        suggested_name = suggested_name[:50]

    # 确保名称不为空
    if not suggested_name:
        return None

    return suggested_name


@app.route('/suggest_folder_name', methods=['POST'])
@performance_monitor_decorator('suggest_folder_name')
def suggest_folder_name():
    """根据文件夹内容智能建议文件夹名称"""
    try:
        # 开始新任务
        start_new_task(f"suggest_name_{int(time.time())}")

        # 清理操作相关缓存
        clear_operation_related_caches(operation_type="renaming")

        folder_id_str = request.form.get('folder_id', '0')

        # 验证文件夹ID
        folder_id, error_msg = validate_folder_id_for_naming(folder_id_str)
        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        logging.info(f"为文件夹 {folder_id} 生成智能命名建议")

        # 检查任务是否被取消
        check_task_cancelled()

        # 获取文件夹中的视频文件（采样处理）
        video_files, sampled_video_files = get_sampled_video_files(folder_id)

        # 准备AI分析的文件列表
        file_list = [{'fileId': item['fileId'], 'filename': item['filename']} for item in sampled_video_files]

        # 使用AI生成文件夹名称建议
        suggested_name = generate_folder_name_with_ai(file_list)

        # 清理和验证建议的名称
        clean_name = clean_suggested_folder_name(suggested_name)

        if clean_name:
            logging.info(f"🤖 AI生成的文件夹名称建议: {clean_name}")
            return jsonify({
                'success': True,
                'suggested_name': clean_name,
                'file_count': len(video_files)
            })
        else:
            return jsonify({'success': False, 'error': 'AI未能生成有效的文件夹名称建议'})

    except TaskCancelledException:
        logging.info("🛑 文件夹命名建议任务被用户取消")
        return jsonify({'success': False, 'error': '任务已被用户取消', 'cancelled': True})
    except (ValidationError, FileSystemError, AIServiceError) as e:
        logging.error(f"智能文件夹命名失败: {e}")
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        logging.error(f"智能文件夹命名时发生未知错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'系统内部错误: {str(e)}'})

@app.route('/organize_files_by_groups', methods=['POST'])
def organize_files_by_groups():
    """根据movie_info智能分组并移动文件"""
    try:
        folder_id_str = request.form.get('folder_id', '0')
        create_subfolders = request.form.get('create_subfolders', 'true').lower() == 'true'

        # 验证文件夹ID
        folder_id, error_msg = validate_folder_id(folder_id_str)
        if error_msg:
            return jsonify({'success': False, 'error': error_msg})

        logging.info(f"开始整理文件夹 {folder_id} 的文件分组")

        # 获取文件夹属性和movie_info
        video_files = []
        try:
            get_video_files_recursively(folder_id, video_files)
        except Exception as e:
            logging.error(f"递归获取视频文件时发生错误: {e}")
            return jsonify({'success': False, 'error': f'获取文件列表失败: {str(e)}'})

        if not video_files:
            return jsonify({'success': False, 'error': '文件夹中没有找到视频文件'})

        # 生成movie_info分组 - 使用重构后的函数
        logging.info(f"📊 开始智能文件分组，共 {len(video_files)} 个文件")

        # 调用重构后的分组处理函数
        logging.info(f"🎯 开始调用智能分组处理函数，文件数量: {len(video_files)}")
        logging.info(f"🔧 使用AI模型: {GROUPING_MODEL}")
        logging.info(f"🌐 API地址: {AI_API_URL}")

        movie_info = process_files_for_grouping(video_files, f"文件夹{folder_id}")

        if not movie_info:
            logging.warning("⚠️ 智能分组未生成任何有效分组，尝试重试机制")
            logging.info(f"🔍 诊断信息 - API密钥状态: {'已配置' if AI_API_KEY else '未配置'}")
            logging.info(f"🔍 诊断信息 - API地址: {AI_API_URL}")
            logging.info(f"🔍 诊断信息 - 分组模型: {GROUPING_MODEL}")

            # 如果第一次失败，尝试重试
            max_retries = GROUPING_MAX_RETRIES
            for attempt in range(max_retries):
                try:
                    logging.info(f"🔄 重试智能分组 (第 {attempt + 1}/{max_retries} 次)")
                    time.sleep(GROUPING_RETRY_DELAY)  # 使用全局配置的重试延迟
                    movie_info = process_files_for_grouping(video_files, f"文件夹{folder_id}_重试{attempt+1}")
                    if movie_info:
                        logging.info(f"✅ 重试成功，获得 {len(movie_info)} 个分组")
                        break
                except Exception as e:
                    logging.error(f"第 {attempt + 1} 次重试失败: {e}")
                    continue

        if not movie_info or not isinstance(movie_info, list) or len(movie_info) == 0:
            error_msg = '无法分析文件分组信息。可能原因：1) AI API连接失败 2) 模型不可用 3) 文件名格式无法识别。请检查AI配置或稍后重试。'
            logging.error(f"❌ 智能分组完全失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg})

        successful_operations = []
        failed_operations = []

        if create_subfolders:
            # 创建子文件夹并移动文件
            for group in movie_info:
                group_name = group.get('group_name', '未知分组')
                # 兼容不同的字段名称
                file_ids = group.get('fileIds', []) or group.get('files', [])

                if not file_ids:
                    continue

                try:
                    # 创建子文件夹
                    folder_result = create_folder_in_cloud(group_name, folder_id)
                    if folder_result:
                        new_folder_id = folder_result.get('dirID')
                        if new_folder_id:
                            # 移动文件到新文件夹
                            move_result = move(file_ids, new_folder_id)
                            if move_result.get('success'):
                                successful_operations.append({
                                    'group_name': group_name,
                                    'folder_id': new_folder_id,
                                    'file_count': len(file_ids),
                                    'operation': 'created_and_moved'
                                })
                            else:
                                failed_operations.append({
                                    'group_name': group_name,
                                    'error': f'移动文件失败: {move_result.get("message", "未知错误")}'
                                })
                        else:
                            failed_operations.append({
                                'group_name': group_name,
                                'error': '创建文件夹成功但未返回文件夹ID'
                            })
                    else:
                        failed_operations.append({
                            'group_name': group_name,
                            'error': '创建文件夹失败'
                        })

                except Exception as e:
                    logging.error(f"处理分组 {group_name} 时发生错误: {e}")
                    failed_operations.append({
                        'group_name': group_name,
                        'error': str(e)
                    })

        # 返回结果
        if create_subfolders:
            total_successful = len(successful_operations)
            total_failed = len(failed_operations)

            logging.info(f"文件整理完成: 成功 {total_successful} 个分组，失败 {total_failed} 个分组")

            return jsonify({
                'success': total_failed == 0,
                'message': f'文件整理完成: 成功处理 {total_successful} 个分组' + (f'，失败 {total_failed} 个分组' if total_failed > 0 else ''),
                'successful_count': total_successful,
                'failed_count': total_failed,
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'movie_info': movie_info,
                'video_files': video_files,
                'count': len(video_files),
                'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB"
            })
        else:
            # 只返回分组信息，不执行文件移动
            logging.info(f"返回分组建议: {len(movie_info)} 个分组")
            return jsonify({
                'success': True,
                'message': f'发现 {len(movie_info)} 个建议分组',
                'movie_info': movie_info,
                'video_files': video_files,
                'count': len(video_files),
                'size': f"{sum(file.get('size', 0) for file in video_files) / (1024**3):.1f}GB"
            })

    except Exception as e:
        logging.error(f"智能文件分组时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create_folder', methods=['POST'])
def create_folder():
    """创建新文件夹"""
    try:
        folder_name = request.form.get('folder_name')
        parent_id = request.form.get('parent_id', '0')

        if not folder_name:
            return jsonify({'success': False, 'error': '文件夹名称不能为空。'})

        # 验证文件夹名称
        folder_name = folder_name.strip()
        if not folder_name:
            return jsonify({'success': False, 'error': '文件夹名称不能为空。'})

        # 检查文件夹名称是否包含非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in folder_name:
                return jsonify({'success': False, 'error': f'文件夹名称不能包含字符: {char}'})

        try:
            parent_id = int(parent_id)
        except ValueError:
            parent_id = 0

        logging.info(f"📁 准备创建文件夹: {folder_name}，父目录ID: {parent_id}")

        # 使用123pan API创建文件夹
        try:
            result = create_folder_in_cloud(folder_name, parent_id)

            if result:
                dir_id = result.get('dirID') if result else None
                logging.info(f"✅ 文件夹创建成功: {folder_name}，新文件夹ID: {dir_id}")
                return jsonify({
                    'success': True,
                    'message': f'文件夹 "{folder_name}" 创建成功',
                    'dir_id': dir_id
                })
            else:
                logging.error(f"创建文件夹失败: API返回空结果")
                return jsonify({'success': False, 'error': '创建文件夹失败'})

        except Exception as api_error:
            logging.error(f"调用123pan API创建文件夹时发生错误: {api_error}", exc_info=True)
            return jsonify({'success': False, 'error': f'API调用失败: {str(api_error)}'})

    except Exception as e:
        logging.error(f"创建文件夹时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/restart', methods=['POST'])
def restart_app():
    """重启应用程序"""
    logging.info("接收到重启应用程序的请求。")
    try:
        response = jsonify({'success': True, 'message': '应用程序正在重启...'})

        def restart_process_async():
            time.sleep(1)
            print("Initiating new process...")
            try:
                # 检测是否为打包环境
                is_packaged = getattr(sys, 'frozen', False)

                if is_packaged:
                    # 打包环境：使用当前可执行文件路径
                    if hasattr(sys, '_MEIPASS'):
                        # PyInstaller打包环境
                        executable_path = sys.executable
                        # 尝试获取原始可执行文件路径
                        if len(sys.argv) > 0 and os.path.exists(sys.argv[0]):
                            executable_path = sys.argv[0]
                        elif os.path.exists(os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-mac')):
                            executable_path = os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-mac')
                        elif os.path.exists(os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-win.exe')):
                            executable_path = os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-win.exe')
                        elif os.path.exists(os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-linux')):
                            executable_path = os.path.join(os.path.dirname(sys.executable), 'pan123-scraper-linux')

                        command = [executable_path]
                        print(f"打包环境重启命令: {command}")
                    else:
                        # 其他打包环境
                        command = [sys.executable]
                else:
                    # 开发环境：使用Python解释器
                    command = [sys.executable] + sys.argv
                    print(f"开发环境重启命令: {command}")

                # 启动新进程
                subprocess.Popen(command,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                cwd=os.getcwd())
                print("New process started. Exiting old process.")

                # 延迟退出，确保响应发送完成
                time.sleep(0.5)
                os._exit(0)

            except Exception as e:
                print(f"Failed to start new process: {e}")
                logging.error(f"重启进程失败: {e}", exc_info=True)

                # 备用重启方法：使用安全的subprocess
                try:
                    print("尝试备用重启方法...")
                    if is_packaged:
                        if sys.platform == "darwin":  # macOS
                            subprocess.Popen(["nohup", "./pan123-scraper-mac"],
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                        elif sys.platform == "win32":  # Windows
                            subprocess.Popen(["pan123-scraper-win.exe"],
                                           creationflags=subprocess.CREATE_NEW_CONSOLE)
                        else:  # Linux
                            subprocess.Popen(["nohup", "./pan123-scraper-linux"],
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                    else:
                        # 开发环境
                        subprocess.Popen([sys.executable] + sys.argv,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)

                    print("备用重启方法执行完成")
                    time.sleep(0.5)
                    os._exit(0)
                except Exception as backup_e:
                    print(f"备用重启方法也失败: {backup_e}")
                    logging.error(f"备用重启方法失败: {backup_e}", exc_info=True)

        Thread(target=restart_process_async).start()
        return response
    except Exception as e:
        logging.error(f"重启应用程序失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'重启失败: {str(e)}'})

@app.route('/restart_status', methods=['GET'])
def restart_status():
    """检查重启功能状态"""
    try:
        is_packaged = getattr(sys, 'frozen', False)

        status = {
            'restart_available': True,
            'environment': 'packaged' if is_packaged else 'development',
            'platform': sys.platform,
            'executable_path': sys.executable,
            'argv': sys.argv,
            'working_directory': os.getcwd()
        }

        if is_packaged:
            # 检查可执行文件是否存在
            possible_executables = []
            if sys.platform == "darwin":
                possible_executables = [
                    './pan123-scraper-mac',
                    'pan123-scraper-mac',
                    './dist/pan123-scraper-mac',
                    'dist/pan123-scraper-mac',
                    sys.executable  # 当前运行的可执行文件
                ]
            elif sys.platform == "win32":
                possible_executables = [
                    './pan123-scraper-win.exe',
                    'pan123-scraper-win.exe',
                    './dist/pan123-scraper-win.exe',
                    'dist/pan123-scraper-win.exe',
                    sys.executable
                ]
            else:
                possible_executables = [
                    './pan123-scraper-linux',
                    'pan123-scraper-linux',
                    './dist/pan123-scraper-linux',
                    'dist/pan123-scraper-linux',
                    sys.executable
                ]

            executable_found = False
            for exe in possible_executables:
                if os.path.exists(exe):
                    status['detected_executable'] = os.path.abspath(exe)
                    executable_found = True
                    break

            # 如果当前就是从可执行文件启动的，那么重启功能应该可用
            if not executable_found and sys.executable and os.path.exists(sys.executable):
                status['detected_executable'] = sys.executable
                executable_found = True

            if not executable_found:
                status['restart_available'] = False
                status['error'] = '未找到可执行文件'
            else:
                # 额外检查：确保检测到的可执行文件有执行权限
                detected_exe = status.get('detected_executable')
                if detected_exe and not os.access(detected_exe, os.X_OK):
                    status['restart_available'] = False
                    status['error'] = f'可执行文件缺少执行权限: {detected_exe}'

        return jsonify(status)
    except Exception as e:
        logging.error(f"检查重启状态失败: {e}", exc_info=True)
        return jsonify({
            'restart_available': False,
            'error': f'状态检查失败: {str(e)}'
        })

@app.route('/delete_empty_folders', methods=['POST'])
def delete_empty_folders():
    """删除指定文件夹下的所有空文件夹或不包含视频文件的文件夹"""
    try:
        folder_id = request.form.get('folder_id', '0')

        # 验证输入
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        try:
            folder_id = int(folder_id)
        except ValueError:
            return jsonify({'success': False, 'error': '文件夹ID必须是数字'})

        logging.info(f"开始删除文件夹 {folder_id} 下的空文件夹或不包含视频文件的文件夹")

        # 递归获取所有子文件夹
        def get_all_subfolders(parent_id):
            """递归获取所有子文件夹"""
            all_folders = []
            try:
                # 使用现有的 list_all_files 函数
                folder_content = get_all_files_in_folder(parent_id, limit=100)
                for item in folder_content:
                    if item.get('type') == 1:  # 文件夹
                        folder_info = {
                            'fileId': item['fileId'],
                            'filename': item['filename'],
                            'parentFileId': item['parentFileId']
                        }
                        all_folders.append(folder_info)
                        # 递归获取子文件夹
                        sub_folders = get_all_subfolders(item['fileId'])
                        all_folders.extend(sub_folders)
            except Exception as e:
                logging.error(f"获取子文件夹失败: {e}")

            return all_folders

        # 检查文件夹是否为空或不包含视频文件
        def is_folder_empty_or_no_videos(folder_id):
            """检查文件夹是否为空或不包含视频文件"""
            try:
                # 使用现有的 list_all_files 函数
                folder_content = get_all_files_in_folder(folder_id, limit=100)

                # 如果文件夹完全为空，可以删除
                if len(folder_content) == 0:
                    return True

                # 检查是否包含视频文件
                has_video_files = False
                for item in folder_content:
                    if item.get('type') == 0:  # 文件类型
                        filename = item.get('filename', '').lower()
                        if any(filename.endswith(ext) for ext in SUPPORTED_MEDIA_TYPES):
                            has_video_files = True
                            break

                # 如果不包含视频文件，可以删除
                return not has_video_files

            except Exception as e:
                logging.error(f"检查文件夹是否包含视频文件失败: {e}")
                return False

        # 删除文件夹
        def delete_folder(folder_id):
            """删除指定的文件夹"""
            try:
                # 使用现有的 delete 函数
                result = delete([folder_id])
                return result.get('success', False)
            except Exception as e:
                logging.error(f"删除文件夹失败: {e}")
                return False

        # 获取所有子文件夹
        all_folders = get_all_subfolders(folder_id)
        logging.info(f"找到 {len(all_folders)} 个子文件夹")

        # 按深度排序，从最深的开始删除（避免删除父文件夹后子文件夹无法访问）
        # 这里简单按fileId倒序排序，通常fileId越大的文件夹越深
        all_folders.sort(key=lambda x: x['fileId'], reverse=True)

        deleted_count = 0
        for folder in all_folders:
            if is_folder_empty_or_no_videos(folder['fileId']):
                if delete_folder(folder['fileId']):
                    deleted_count += 1
                    logging.info(f"删除空文件夹或无视频文件夹: {folder['filename']} (ID: {folder['fileId']})")
                else:
                    logging.warning(f"删除文件夹失败: {folder['filename']} (ID: {folder['fileId']})")

        logging.info(f"删除空文件夹或无视频文件夹完成，共删除 {deleted_count} 个文件夹")
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'成功删除 {deleted_count} 个空文件夹或无视频文件夹'
        })

    except Exception as e:
        logging.error(f"删除空文件夹时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/execute_selected_groups', methods=['POST'])
def execute_selected_groups():
    """执行选中的分组"""
    try:
        folder_id = request.form.get('folder_id', '0')
        selected_groups_json = request.form.get('selected_groups')

        # 验证输入
        if not folder_id or folder_id == 'null' or folder_id == 'undefined':
            return jsonify({'success': False, 'error': '无效的文件夹ID'})

        if not selected_groups_json:
            return jsonify({'success': False, 'error': '没有选择要执行的分组'})

        try:
            folder_id = int(folder_id)
            selected_groups = json.loads(selected_groups_json)
        except (ValueError, json.JSONDecodeError) as e:
            return jsonify({'success': False, 'error': f'数据格式错误: {e}'})

        logging.info(f"开始执行选中的分组，文件夹ID: {folder_id}，选中分组数: {len(selected_groups)}")

        success_count = 0
        failed_count = 0

        for group in selected_groups:
            try:
                # 获取分组名称和文件ID列表
                group_name = group.get('group_name', '')
                # 兼容不同的字段名称：fileIds 或 files
                file_ids = group.get('fileIds', []) or group.get('files', [])

                if not group_name or not file_ids:
                    logging.warning(f"⚠️ 跳过无效分组: group_name='{group_name}', file_ids={len(file_ids) if file_ids else 0}, 原始数据: {group}")
                    failed_count += 1
                    continue

                logging.info(f"🎯 准备执行分组 '{group_name}': {len(file_ids)} 个文件")

                # 创建文件夹（如果已存在会返回现有文件夹ID）
                result = create_folder_in_cloud(group_name, folder_id)
                if result and 'data' in result and result['data'] and result['data'].get('dirID'):
                    target_folder_id = result['data']['dirID']
                    logging.info(f"📁 使用文件夹 '{group_name}'，ID: {target_folder_id}")

                    # 移动文件到目标文件夹
                    move_result = move(file_ids, target_folder_id)
                    if move_result.get('success', False):
                        success_count += 1
                        logging.info(f"✅ 成功执行分组 '{group_name}': 移动了 {len(file_ids)} 个文件到文件夹 {target_folder_id}")
                    else:
                        failed_count += 1
                        logging.error(f"❌ 移动文件失败，分组 '{group_name}': {move_result}")
                else:
                    failed_count += 1
                    logging.error(f"❌ 创建/获取文件夹失败，分组 '{group_name}': {result}")

            except Exception as e:
                failed_count += 1
                logging.error(f"执行分组时发生错误: {e}", exc_info=True)

        logging.info(f"分组执行完成: 成功 {success_count} 个分组，失败 {failed_count} 个分组")
        return jsonify({
            'success': True,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'分组执行完成: 成功 {success_count} 个，失败 {failed_count} 个'
        })

    except Exception as e:
        logging.error(f"执行选中分组时发生错误: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

def get_process_using_port(port):
    """获取占用指定端口的进程信息"""
    import subprocess
    import sys

    try:
        # 验证端口号是否为有效整数
        if not isinstance(port, int) or port < 1 or port > 65535:
            logging.warning(f"无效的端口号: {port}")
            return None

        if sys.platform == "win32":
            # Windows系统使用netstat命令（安全版本）
            result = subprocess.run(["netstat", "-ano"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            return int(pid) if pid.isdigit() else None
        else:
            # Linux/macOS系统使用lsof命令（安全版本）
            result = subprocess.run(["lsof", f"-ti:{port}"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                return int(pid) if pid.isdigit() else None
    except Exception as e:
        logging.debug(f"获取端口 {port} 占用进程信息失败: {e}")

    return None


def kill_process_by_pid(pid):
    """根据PID结束进程"""
    import subprocess
    import sys

    try:
        # 验证PID是否为有效整数
        if not isinstance(pid, int) or pid <= 0:
            logging.warning(f"无效的PID: {pid}")
            return False

        if sys.platform == "win32":
            # Windows系统使用taskkill命令（安全版本）
            result = subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        else:
            # Linux/macOS系统使用kill命令（安全版本）
            result = subprocess.run(["kill", "-9", str(pid)],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
    except Exception as e:
        logging.error(f"结束进程 {pid} 失败: {e}")
        return False


def get_process_name_by_pid(pid):
    """根据PID获取进程名称"""
    import subprocess
    import sys

    try:
        # 验证PID是否为有效整数
        if not isinstance(pid, int) or pid <= 0:
            logging.warning(f"无效的PID: {pid}")
            return "无效PID"

        if sys.platform == "win32":
            # Windows系统使用tasklist命令（安全版本）
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if lines:
                    # CSV格式：进程名,PID,会话名,会话号,内存使用
                    parts = lines[0].split(',')
                    if len(parts) >= 1:
                        return parts[0].strip('"')
        else:
            # Linux/macOS系统使用ps命令（安全版本）
            result = subprocess.run(["ps", "-p", str(pid), "-o", "comm="],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except Exception as e:
        logging.debug(f"获取进程 {pid} 名称失败: {e}")

    return "未知进程"


def kill_port_process(port, force=True):
    """结束占用指定端口的进程

    Args:
        port (int): 端口号
        force (bool): 是否强制结束进程

    Returns:
        bool: 是否成功结束进程
    """
    try:
        pid = get_process_using_port(port)
        if pid is None:
            logging.debug(f"端口 {port} 未被占用")
            return True

        process_name = get_process_name_by_pid(pid)
        logging.info(f"🔍 检测到端口 {port} 被进程占用: PID={pid}, 进程名={process_name}")

        # 检查是否是自己的进程（避免误杀）
        current_pid = os.getpid()
        if pid == current_pid:
            logging.warning(f"⚠️ 检测到占用端口的是当前进程，跳过结束操作")
            return False

        if force:
            logging.info(f"🔪 正在结束占用端口 {port} 的进程: PID={pid}, 进程名={process_name}")
            success = kill_process_by_pid(pid)
            if success:
                logging.info(f"✅ 成功结束进程: PID={pid}, 进程名={process_name}")
                # 等待一小段时间确保端口释放
                import time
                time.sleep(1)
                return True
            else:
                logging.error(f"❌ 结束进程失败: PID={pid}, 进程名={process_name}")
                return False
        else:
            logging.info(f"ℹ️ 发现占用端口 {port} 的进程: PID={pid}, 进程名={process_name}，但未设置强制结束")
            return False

    except Exception as e:
        logging.error(f"处理端口 {port} 占用进程时发生错误: {e}")
        return False


def find_available_port(start_port=5001, max_attempts=10, kill_occupied=True):
    """查找可用端口，可选择结束占用进程

    Args:
        start_port (int): 起始端口号
        max_attempts (int): 最大尝试次数
        kill_occupied (bool): 是否结束占用端口的进程

    Returns:
        int or None: 可用端口号，如果找不到则返回None
    """
    import socket

    # 首先尝试默认端口
    if kill_occupied:
        logging.info(f"🔍 检查端口 {start_port} 是否被占用...")
        if kill_port_process(start_port):
            # 尝试使用释放的端口
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', start_port))
                    logging.info(f"✅ 端口 {start_port} 现在可用")
                    return start_port
            except OSError:
                logging.warning(f"⚠️ 端口 {start_port} 仍然被占用")

    # 如果默认端口不可用，查找其他端口
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            if kill_occupied and port == start_port:
                # 已经尝试过结束进程，跳过
                continue
            continue

    return None

def start_flask_app():
    """启动Flask应用，带错误处理"""
    logging.info("启动 Flask 应用程序。")

    # 获取端口配置
    default_port = int(os.environ.get('PORT', 5001))

    # 检查是否启用自动结束占用进程功能
    kill_occupied_process = app_config.get('KILL_OCCUPIED_PORT_PROCESS', True)

    if kill_occupied_process:
        logging.info(f"🔍 启用自动结束占用端口进程功能")
    else:
        logging.info(f"ℹ️ 自动结束占用端口进程功能已禁用")

    # 检查端口是否可用，可选择结束占用进程
    available_port = find_available_port(default_port, kill_occupied=kill_occupied_process)
    if available_port is None:
        logging.error(f"❌ 无法找到可用端口（尝试范围：{default_port}-{default_port+9}）")
        if not kill_occupied_process:
            logging.info(f"💡 提示：可以在配置中启用 'KILL_OCCUPIED_PORT_PROCESS' 来自动结束占用端口的进程")
        return

    if available_port != default_port:
        if kill_occupied_process:
            logging.info(f"🔄 端口 {default_port} 处理完成，使用端口 {available_port}")
        else:
            logging.warning(f"⚠️ 端口 {default_port} 被占用，使用端口 {available_port}")

    logging.info(f"🌐 启动服务器，端口: {available_port}")

    try:
        # 启动缓存清理后台任务
        start_cache_cleanup_task()

        # 检测是否为打包环境
        import sys
        is_packaged = getattr(sys, 'frozen', False)
        debug_mode = not is_packaged  # 打包环境下禁用调试模式

        if is_packaged:
            logging.info("🎁 检测到打包环境，禁用调试模式")

        app.run(debug=debug_mode, port=available_port, host='0.0.0.0', threaded=True, use_reloader=False)

    except OSError as e:
        if "Address already in use" in str(e):
            logging.error(f"❌ 端口 {available_port} 被占用，尝试查找其他端口...")
            # 递归尝试下一个端口
            os.environ['PORT'] = str(available_port + 1)
            start_flask_app()
        else:
            logging.error(f"❌ 启动服务器时发生错误: {e}")
    except Exception as e:
        logging.error(f"❌ 应用启动失败: {e}", exc_info=True)

if __name__ == '__main__':
    start_flask_app()







