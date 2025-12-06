# handleCNY.py


class ChangeCNY(object):
    NUM_DICT = {
        "0": "零",
        "1": "壹",
        "2": "贰",
        "3": "叁",
        "4": "肆",
        "5": "伍",
        "6": "陆",
        "7": "柒",
        "8": "捌",
        "9": "玖",
        "10": "拾",
        "100": "佰",
        "1000": "仟",
    }
    CN_TO_NUM = {item[1]: item[0] for item in NUM_DICT.items()}
    VALIDATE_CN = [item[1] for item in NUM_DICT.items()] + [
        "分",
        "角",
        "元",
        "拾",
        "佰",
        "仟",
        "万",
        "亿",
        "兆",
        "整",
    ]
    MIN_CN = ["角", "分"]

    def validate(self, val, small=True):
        """金额验证器
        args：
            val str：输入的金额
            small bool：小写金额为True，大写金额为False
        returns：
            str/tuple：返回一个验证后的字符串或列表，验证的是大写金额时返回字符串；否则返回小写金额元组(整数部分, 小数部分)
        """
        err = ""

        if not isinstance(val, str):
            raise ValueError("传入的类型错误，期待一个字符串类型。")

        if small:
            target = val.split(".")
            if len(target) > 2:
                raise ValueError("传入的值错误，异常的小写金额。")
            if len(target[0]) > 16:
                raise ValueError("输入金额超限，无法计算。")
            if len(target) > 1 and len(target[1]) > 2:
                raise ValueError("传入的值错误，小数部分不能超过三位。")
            for item in target:
                if not item.isnumeric():
                    err = "传入的值错误，异常的小写金额。"
                    break
            if err:
                raise ValueError(err)
            res = (target[0], target[1]) if len(target) > 1 else (target[0], 0)
            return res

        for s in val:
            if s not in self.VALIDATE_CN:
                err = "传入的值错误，异常的大写金额。"
        if err:
            raise ValueError(err)
        return val

    def small_to_big(self, small):
        """将小写金额转换成大写金额的方法
        args：
            small str：接收一个小写金额字符串
        returns：
            str：返回一个大写的人民币金额
        """
        max, min = self.validate(val=small)
        # 处理小数部分
        if min:
            min_str = ""
            for index, num in enumerate(min):
                min_str += "%s%s" % (self.NUM_DICT[num], self.MIN_CN[index])
        else:
            min_str = "整"
        # 处理整数部分
        big_str = ""
        change_swap = ["", "拾", "佰", "仟"]
        unit_swap = ["元", "万", "亿", "兆"]
        for index, num in enumerate(max[::-1]):
            if index % 4 == 0:
                change_swap[0] = unit_swap[index // 4]
                # 如果刚好关键位为0，那就是不给零，只给标志位
                if num == "0":
                    big_str += change_swap[index % 4]
                    continue
                big_str += "%s%s" % (change_swap[index % 4], self.NUM_DICT[num])
            else:
                if num == "0":
                    big_str += self.NUM_DICT[num]
                    continue
                big_str += "%s%s" % (change_swap[index % 4], self.NUM_DICT[num])
        # 去掉多于的零
        big_str = big_str[::-1]
        # print(big_str)
        tmp_str = ""
        for i in range(len(big_str)):
            if i == len(big_str):
                continue
            if big_str[i] == "零" and big_str[i + 1] == "零":
                continue
            if big_str[i] == "零" and big_str[i + 1] in unit_swap:
                continue
            tmp_str += big_str[i]
        # 整合整数部分和小数部分返回
        return tmp_str + min_str

    def __call_handle_big(self, big_str):
        """一个用于处理整数大写金额的递归函数
        args：
            big_str str：接收一个大写的整数金额
        returns：
            str：返回一个小写的金额字符串
        """
        min_ls = []
        max_unit = ""
        unit_swap = {"元": 1, "万": 5, "亿": 9, "兆": 13}
        for s in unit_swap:
            if s in big_str:
                if len(min_ls) < unit_swap[s]:
                    min_ls = ["" for _ in range(unit_swap[s])]
                    max_unit = s
        if len(big_str.split(max_unit)) > 1:
            front, back = big_str.split(max_unit)[0], big_str.split(max_unit)[1]
        else:
            front, back = big_str.split(max_unit)[0], []
        tmp_ls = []
        inner_ls = []
        for cn in front:
            if cn != "零":
                inner_ls.append(self.CN_TO_NUM[cn])
            else:
                tmp_ls.append(inner_ls)
                inner_ls = []
        tmp_ls.append(inner_ls)
        all_tp = 0
        for need_calc in tmp_ls:
            tp = 0
            for i in range(len(need_calc)):
                # 是最后一个数据，并且是奇数的时候
                if i + 1 == len(need_calc) and (i + 1) % 2 != 0:
                    tp += int(need_calc[i])
                if (i + 1) % 2 == 0:
                    tp += int(need_calc[i]) * int(need_calc[i - 1])
            all_tp += tp
        all_tp = str(all_tp)
        if len(all_tp) != 4:
            all_tp = ("0" * (4 - len(all_tp))) + all_tp
        if not back:
            return all_tp
        else:
            return all_tp + self.__call_handle_big(back)

    def big_to_small(self, big):
        """将大写金额转为小写金额的方法
        args：
            big str：接收一个大写金额字符串，支持有小数的金额
        returns：
            str：返回一个小写金额字符串
        """
        big_str = self.validate(big, small=False)
        # 初始化小数和整数部分
        dec = ""
        get_int = ""
        if "整" in big_str:
            get_int = self.__call_handle_big(big_str[:-1])
        else:
            # 处理小数部分
            if big_str[-1] == "分":
                dec = ".%s%s" % (
                    self.CN_TO_NUM[big_str[-4]],
                    self.CN_TO_NUM[big_str[-2]],
                )
                get_int = self.__call_handle_big(big_str[:-4])
            else:
                dec = ".%s" % (self.CN_TO_NUM[big_str[-2]])
                get_int = self.__call_handle_big(big_str[:-2])
        # 去掉整数前面多于的零
        remove_index = 0
        for s in get_int:
            if s != "0":
                break
            remove_index += 1
        res_small = get_int[remove_index:] + dec
        return res_small


if __name__ == "__main__":
    change = ChangeCNY()
    while 1:
        small = input("请输入小写金额(退出请输入Q/q)：")
        if small.lower() == "q":
            print("Bye...")
            break
        # print(f'输入的金额：{small}')
        print(f"大写金额为：{change.small_to_big(small)}")
        # print(f'再次变换为：{change.big_to_small(change.small_to_big(small))}')
