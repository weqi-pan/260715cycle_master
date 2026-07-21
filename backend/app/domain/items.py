"""道具唯一运行时定义源。"""

ITEM_NAMES = {
    "item_amulet": "阿六的护身符", "item_tunnel_map": "密道地图",
    "item_sutra": "慧觉经文残片", "item_beads": "菩提子念珠",
    "item_talisman": "镇魂符纸", "item_notebook_page": "张天民笔记(单页)",
    "item_notebook_full": "张天民笔记(完整)", "item_old_key": "锈蚀铜钥匙",
    "item_lion_inscription": "铜狮底座拓片", "item_qing_coin": "清代顺治通宝",
    "item_warning_note": "警告便签", "item_old_newspaper": "1993年旧报纸",
    "item_broken_mirror": "八卦铜镜碎片", "item_incense_stub": "香炉残香",
    "item_merit_stele_photo": "功德碑照片", "item_old_photo": "糖水铺老照片",
    "item_porcelain_shard": "青花瓷碎片", "item_old_doorplate": "第十二甫旧门牌",
    "item_black_jade": "墨玉吊坠", "item_graffiti_photo": "消防栓涂鸦照片",
    "item_hardhat": "施工安全帽", "item_river_porcelain": "明代青花碗底残片",
    "item_shamian_doorplate": "沙面法文老门牌", "item_river_lantern_note": "河灯感谢纸条",
    "item_scholar_diary": "陈伯陶日记", "item_family_tree": "陈氏家族谱系图",
    "item_rainbow_stone": "老榕树下雨花石", "item_loop_newspaper": "循环报纸",
    "item_joss_paper": "冥纸残片", "item_jade_pendant": "李氏传家玉佩",
    "item_chen_letter": "陈伯陶回信", "item_shrine_incense": "路边神龛香灰",
    "item_milk_tea_receipt": "便利店奶茶收据", "item_ferry_ticket": "珠江轮渡旧船票",
    "item_fossil_pipe": "石化烟斗", "item_photo_negative": "老照相馆底片",
    "item_bridge_coin": "天桥许愿硬币", "item_anshen_herb": "安神药包",
    "item_rooftop_tile": "天台红瓦片", "item_denim_rag": "一块破布",
}

DISCARDABLE_ITEMS = {
    "item_qing_coin", "item_denim_rag", "item_warning_note", "item_old_newspaper",
}

CROSS_SURFACE_ITEMS = {
    "item_amulet", "item_qing_coin", "item_beads", "item_porcelain_shard",
    "item_denim_rag", "item_jade_pendant",
}


def item_definition(item_id: str) -> dict:
    """返回可随 Frame/存档安全序列化的规范道具元数据。"""
    if item_id not in ITEM_NAMES:
        raise ValueError(f"Unknown item: {item_id}")
    return {
        "id": item_id,
        "name": ITEM_NAMES[item_id],
        "discardable": item_id in DISCARDABLE_ITEMS,
        "cross_surface": item_id in CROSS_SURFACE_ITEMS,
    }
