import re
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import getpass

class Config:
    DEFAULT_DATA_DIR = Path.home() / "PhoneAccountSystem"
    BACKUP_COUNT = 10
    MAX_AUTH_ATTEMPTS = 3
    MIN_ANSWER_LENGTH = 2
    DEFAULT_REGISTRATION_BONUS = 50.0  # 默认奖励金额

class NavigationManager:
    @staticmethod
    def show_back_option():
        print("\n0. 返回上一步")
    
    @staticmethod
    def handle_back_choice(choice):
        return choice == '0'

class SecurityManager:
    @staticmethod
    def validate_phone(phone):
        pattern = r'^1[3-9]\d{9}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def validate_password(password):
        return len(password) == 4 and password.isdigit()
    
    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def hash_answer(answer):
        return hashlib.sha256(answer.strip().lower().encode()).hexdigest()
    
    @staticmethod
    def verify_password(input_password, stored_hash):
        return SecurityManager.hash_password(input_password) == stored_hash
    
    @staticmethod
    def verify_answer(input_answer, stored_hash):
        return SecurityManager.hash_answer(input_answer) == stored_hash

class TimeManager:
    @staticmethod
    def get_current_time():
        return datetime.now().isoformat()
    
    @staticmethod
    def parse_time(time_str):
        return datetime.fromisoformat(time_str)
    
    @staticmethod
    def calculate_expiry_time(valid_days):
        expiry = datetime.now() + timedelta(days=valid_days)
        return expiry.isoformat()
    
    @staticmethod
    def is_expired(expiry_time):
        expiry = TimeManager.parse_time(expiry_time)
        return datetime.now() > expiry
    
    @staticmethod
    def get_remaining_days(expiry_time):
        expiry = TimeManager.parse_time(expiry_time)
        now = datetime.now()
        remaining = expiry - now
        return max(0, remaining.days)
    
    @staticmethod
    def format_remaining_time(expiry_time):
        if TimeManager.is_expired(expiry_time):
            return "已过期"
        remaining_days = TimeManager.get_remaining_days(expiry_time)
        if remaining_days == 0:
            expiry = TimeManager.parse_time(expiry_time)
            now = datetime.now()
            remaining_hours = max(0, (expiry - now).seconds // 3600)
            return f"{remaining_hours}小时"
        return f"{remaining_days}天"

class GitHubSyncManager:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path
        self.data_file = "phone_accounts.json"
    
    def init_git_repo(self):
        try:
            if not os.path.exists(os.path.join(self.repo_path, ".git")):
                print("📦 初始化Git仓库...")
                subprocess.run(["git", "init"], cwd=self.repo_path, check=True, 
                             capture_output=True, text=True)
                print("✅ Git仓库初始化完成")
            return True
        except Exception as e:
            print(f"❌ Git初始化失败: {e}")
            return False
    
    def set_remote_url(self, remote_url):
        try:
            result = subprocess.run(["git", "remote", "get-url", "origin"], 
                                  cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                subprocess.run(["git", "remote", "add", "origin", remote_url], 
                             cwd=self.repo_path, check=True)
                print(f"✅ 已设置远程仓库: {remote_url}")
            else:
                subprocess.run(["git", "remote", "set-url", "origin", remote_url], 
                             cwd=self.repo_path, check=True)
                print(f"✅ 已更新远程仓库: {remote_url}")
            return True
        except Exception as e:
            print(f"❌ 设置远程仓库失败: {e}")
            return False
    
    def git_commit_and_push(self, commit_message=None):
        if commit_message is None:
            commit_message = f"更新账户数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        try:
            subprocess.run(["git", "add", self.data_file], 
                         cwd=self.repo_path, check=True, capture_output=True)
            
            status_result = subprocess.run(["git", "status", "--porcelain"], 
                                         cwd=self.repo_path, capture_output=True, text=True)
            
            if not status_result.stdout.strip():
                return True, "没有更改需要提交"
            
            subprocess.run(["git", "commit", "-m", commit_message], 
                         cwd=self.repo_path, check=True, capture_output=True)
            
            print("✅ 本地提交完成")
            
            push_result = subprocess.run(["git", "push", "-u", "origin", "main"], 
                                       cwd=self.repo_path, capture_output=True, text=True)
            
            if push_result.returncode != 0:
                push_result = subprocess.run(["git", "push", "-u", "origin", "master"], 
                                           cwd=self.repo_path, capture_output=True, text=True)
            
            if push_result.returncode == 0:
                print("✅ 已推送到GitHub")
                return True, "GitHub同步成功"
            else:
                return True, "本地提交成功，但推送失败"
                
        except Exception as e:
            return False, f"Git操作失败: {e}"
    
    def git_pull(self):
        try:
            pull_result = subprocess.run(["git", "pull"], 
                                       cwd=self.repo_path, capture_output=True, text=True)
            
            if pull_result.returncode == 0:
                if "Already up to date" in pull_result.stdout:
                    return True, "数据已是最新"
                else:
                    print("✅ 已从GitHub更新数据")
                    return True, "GitHub更新成功"
            else:
                return False, f"拉取失败: {pull_result.stderr}"
        except Exception as e:
            return False, f"Git拉取失败: {e}"
    
    def get_git_status(self):
        try:
            remote_result = subprocess.run(["git", "remote", "-v"], 
                                         cwd=self.repo_path, capture_output=True, text=True)
            status_result = subprocess.run(["git", "status", "--short"], 
                                         cwd=self.repo_path, capture_output=True, text=True)
            
            return {
                "has_remote": bool(remote_result.stdout.strip()),
                "remote_url": remote_result.stdout,
                "has_changes": bool(status_result.stdout.strip())
            }
        except Exception as e:
            return {"error": str(e)}

class BackupManager:
    def __init__(self, data_file, backup_dir):
        self.data_file = data_file
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self):
        if not self.data_file.exists():
            return False
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.json"
            shutil.copy2(self.data_file, backup_file)
            self._cleanup_old_backups()
            return True
        except Exception as e:
            print(f"⚠️ 备份失败: {e}")
            return False
    
    def _cleanup_old_backups(self):
        try:
            backup_files = []
            for file in self.backup_dir.glob("backup_*.json"):
                backup_files.append((file, file.stat().st_mtime))
            backup_files.sort(key=lambda x: x[1], reverse=True)
            for file_path, _ in backup_files[Config.BACKUP_COUNT:]:
                file_path.unlink()
        except Exception as e:
            print(f"⚠️ 备份清理失败: {e}")

class FileStorageManager:
    def __init__(self, data_file, backup_dir):
        self.data_file = data_file
        self.backup_manager = BackupManager(data_file, backup_dir)
    
    def load_data(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"✅ 数据加载成功，共 {len(data)} 个账户")
                return data
            except Exception as e:
                print(f"❌ 数据加载失败: {e}")
                return {}
        else:
            print("📝 创建新数据文件")
            return {}
    
    def save_data(self, data):
        try:
            self.backup_manager.create_backup()
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 数据保存成功")
            return True
        except Exception as e:
            print(f"❌ 数据保存失败: {e}")
            return False

class AccountManager:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.accounts = self.storage_manager.load_data()
    
    def save_data(self):
        return self.storage_manager.save_data(self.accounts)
    
    def set_registration_bonus(self, phone):
        """设置登记奖励金额"""
        print("\n" + "="*30)
        print("🎁 设置登记奖励金额")
        print("="*30)
        print(f"默认奖励金额: {Config.DEFAULT_REGISTRATION_BONUS}元")
        
        while True:
            NavigationManager.show_back_option()
            bonus_input = input("请输入奖励金额 (直接回车使用默认值): ").strip()
            
            if NavigationManager.handle_back_choice(bonus_input):
                return False, "已取消设置奖励金额"
            
            if not bonus_input:
                # 使用默认值
                bonus_amount = Config.DEFAULT_REGISTRATION_BONUS
                print(f"✅ 使用默认奖励金额: {bonus_amount}元")
                return True, bonus_amount
            
            try:
                bonus_amount = float(bonus_input)
                if bonus_amount < 0:
                    print("❌ 奖励金额不能为负数")
                    continue
                elif bonus_amount == 0:
                    print("⚠️ 奖励金额为0，该账户将没有初始余额")
                
                print(f"✅ 设置奖励金额: {bonus_amount}元")
                return True, bonus_amount
                
            except ValueError:
                print("❌ 请输入有效的数字")
    
    def set_valid_days(self, phone):
        print("\n" + "="*30)
        print("⏰ 设置账户有效期")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            valid_days_input = input("请输入有效期天数 (例如：30): ").strip()
            
            if NavigationManager.handle_back_choice(valid_days_input):
                return False, "已取消设置有效期"
            
            try:
                valid_days = int(valid_days_input)
                if valid_days <= 0:
                    print("❌ 有效期必须大于0天")
                    continue
                
                self.accounts[phone]["valid_days"] = valid_days
                self.accounts[phone]["created_at"] = TimeManager.get_current_time()
                self.accounts[phone]["expiry_time"] = TimeManager.calculate_expiry_time(valid_days)
                self.accounts[phone]["status"] = "正常"
                
                print(f"✅ 有效期设置成功: {valid_days}天")
                return True, f"有效期设置成功: {valid_days}天"
                
            except ValueError:
                print("❌ 请输入有效的数字")
    
    def set_password_and_security(self, phone):
        print("\n" + "="*40)
        print("🔐 设置账户安全信息")
        print("="*40)
        
        while True:
            NavigationManager.show_back_option()
            password = getpass.getpass("请设置4位数字密码: ")
            
            if NavigationManager.handle_back_choice(password):
                return False, "已取消设置安全信息"
            
            if not SecurityManager.validate_password(password):
                print("❌ 密码必须是4位数字")
                continue
            
            confirm_password = getpass.getpass("请确认4位数字密码: ")
            if password != confirm_password:
                print("❌ 两次输入的密码不一致")
                continue
            
            self.accounts[phone]["password"] = SecurityManager.hash_password(password)
            break
        
        common_questions = [
            "你最喜欢的颜色是什么？",
            "你的出生城市是？", 
            "你的小学名称是？",
            "你宠物的名字是什么？",
            "你母亲的姓氏是？",
            "你最喜欢的电影是？",
            "你的第一所学校是？",
            "你最好的朋友名字是？"
        ]
        
        print("\n请选择一个密保问题：")
        for i, question in enumerate(common_questions, 1):
            print(f"{i}. {question}")
        
        while True:
            NavigationManager.show_back_option()
            choice = input("请选择问题编号 (1-8): ").strip()
            
            if NavigationManager.handle_back_choice(choice):
                return False, "已取消设置安全信息"
            
            try:
                choice = int(choice)
                if 1 <= choice <= 8:
                    selected_question = common_questions[choice-1]
                    break
                else:
                    print("请输入1-8之间的数字")
            except ValueError:
                print("请输入有效的数字")
        
        while True:
            NavigationManager.show_back_option()
            answer = input("请输入密保答案: ").strip()
            
            if NavigationManager.handle_back_choice(answer):
                return False, "已取消设置安全信息"
            
            if len(answer) < Config.MIN_ANSWER_LENGTH:
                print(f"❌ 答案至少需要{Config.MIN_ANSWER_LENGTH}个字符")
                continue
            
            confirm_answer = input("请确认密保答案: ").strip()
            if answer.lower() != confirm_answer.lower():
                print("❌ 两次输入的答案不一致")
                continue
            
            self.accounts[phone]["security_question"] = selected_question
            self.accounts[phone]["security_answer"] = SecurityManager.hash_answer(answer)
            break
        
        self.accounts[phone]["last_modified"] = TimeManager.get_current_time()
        
        if self.save_data():
            return True, "账户安全信息设置成功"
        else:
            return False, "账户安全信息设置失败"
    
    def check_account_status(self, phone, info):
        if info.get("status") == "已过期":
            return False, "❌ 账户已过期，无法进行操作"
        
        if TimeManager.is_expired(info["expiry_time"]):
            info["status"] = "已过期"
            self.save_data()
            return False, "❌ 账户已过期，无法进行操作"
        
        return True, "账户状态正常"
    
    def authenticate_with_password(self, phone, info):
        status_ok, status_msg = self.check_account_status(phone, info)
        if not status_ok:
            return False, status_msg
        
        attempts = Config.MAX_AUTH_ATTEMPTS
        
        print(f"\n" + "="*20)
        print("🔒 密码验证")
        print("="*20)
        
        while attempts > 0:
            NavigationManager.show_back_option()
            password = getpass.getpass("请输入4位数字密码: ")
            
            if NavigationManager.handle_back_choice(password):
                return False, "已取消操作"
            
            if SecurityManager.verify_password(password, info["password"]):
                print("✅ 密码验证成功")
                return True, "验证成功"
            else:
                attempts -= 1
                if attempts > 0:
                    print(f"❌ 密码错误，还有{attempts}次尝试机会")
                else:
                    print("❌ 密码错误次数过多，操作取消")
                    return False, "密码错误次数过多"
        
        return False, "验证失败"
    
    def authenticate_with_security_question(self, phone, info):
        attempts = Config.MAX_AUTH_ATTEMPTS
        
        print(f"\n" + "="*20)
        print("🔐 密保验证")
        print("="*20)
        print(f"密保问题: {info['security_question']}")
        
        while attempts > 0:
            NavigationManager.show_back_option()
            answer = input("请输入密保答案: ").strip()
            
            if NavigationManager.handle_back_choice(answer):
                return False, "已取消操作"
            
            if SecurityManager.verify_answer(answer, info["security_answer"]):
                print("✅ 密保验证成功")
                return True, "验证成功"
            else:
                attempts -= 1
                if attempts > 0:
                    print(f"❌ 答案错误，还有{attempts}次尝试机会")
                else:
                    print("❌ 答案错误次数过多，操作取消")
                    return False, "答案错误次数过多"
        
        return False, "验证失败"
    
    def reset_password(self, phone, info):
        print("\n" + "="*30)
        print("🔄 密码重置")
        print("="*30)
        
        auth_success, auth_message = self.authenticate_with_security_question(phone, info)
        if not auth_success:
            return False, auth_message
        
        while True:
            NavigationManager.show_back_option()
            new_password = getpass.getpass("请设置新的4位数字密码: ")
            
            if NavigationManager.handle_back_choice(new_password):
                return False, "已取消密码重置"
            
            if not SecurityManager.validate_password(new_password):
                print("❌ 密码必须是4位数字")
                continue
            
            confirm_password = getpass.getpass("请确认新的4位数字密码: ")
            if new_password != confirm_password:
                print("❌ 两次输入的密码不一致")
                continue
            
            info["password"] = SecurityManager.hash_password(new_password)
            info["last_modified"] = TimeManager.get_current_time()
            
            if self.save_data():
                return True, "密码重置成功"
            else:
                return False, "密码重置失败"

class PhoneAccountSystem:
    def __init__(self, data_file=None, github_repo=None):
        if data_file is None:
            self.data_dir = Config.DEFAULT_DATA_DIR
            self.data_dir.mkdir(exist_ok=True)
            self.data_file = self.data_dir / "phone_accounts.json"
            self.backup_dir = self.data_dir / "backups"
        else:
            self.data_file = Path(data_file)
            self.data_dir = self.data_file.parent
            self.backup_dir = self.data_dir / "backups"
        
        print(f"📁 数据目录: {self.data_dir}")
        print(f"📄 数据文件: {self.data_file}")
        
        self.storage_manager = FileStorageManager(self.data_file, self.backup_dir)
        self.account_manager = AccountManager(self.storage_manager)
        
        self.github_enabled = github_repo is not None
        if self.github_enabled:
            self.git_manager = GitHubSyncManager(str(self.data_dir))
            self.git_manager.init_git_repo()
            self.git_manager.set_remote_url(github_repo)
            print("🔗 GitHub同步已启用")
            self.sync_from_github()
    
    def sync_to_github(self):
        if not self.github_enabled:
            return False, "GitHub同步未启用"
        
        success, message = self.git_manager.git_commit_and_push()
        if success:
            print("✅ GitHub同步完成")
        else:
            print(f"⚠️ GitHub同步失败: {message}")
        return success, message
    
    def sync_from_github(self):
        if not self.github_enabled:
            return False, "GitHub同步未启用"
        
        print("🔄 正在从GitHub同步数据...")
        success, message = self.git_manager.git_pull()
        if success:
            print("✅ " + message)
            self.account_manager.accounts = self.storage_manager.load_data()
        else:
            print("⚠️ " + message)
        return success, message
    
    def register_phone(self):
        print("\n" + "="*30)
        print("📝 登记手机号")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            phone = input("请输入手机号: ").strip()
            
            if NavigationManager.handle_back_choice(phone):
                return False, "已取消登记"
            
            if not SecurityManager.validate_phone(phone):
                print("❌ 手机号格式不正确")
                continue
            
            if phone in self.account_manager.accounts:
                print("❌ 该手机号已登记")
                continue
            
            last_four = phone[-4:]
            
            tail_conflict = False
            for existing_phone, info in self.account_manager.accounts.items():
                if info.get("last_four") == last_four:
                    print(f"❌ 尾号{last_four}已被手机号{existing_phone}使用")
                    tail_conflict = True
                    break
            
            if tail_conflict:
                continue
            
            # 设置奖励金额
            success, bonus_result = self.account_manager.set_registration_bonus(phone)
            if not success:
                return False, bonus_result
            
            bonus_amount = bonus_result
            
            # 创建账户
            self.account_manager.accounts[phone] = {
                "balance": bonus_amount,
                "last_four": last_four,
                "password": None,
                "security_question": None,
                "security_answer": None,
                "status": "未设置有效期",
                "registration_bonus": bonus_amount  # 记录奖励金额
            }
            
            print(f"✅ 手机号 {phone} 登记成功，尾号 {last_four}")
            print(f"🎁 获得登记奖励: +{bonus_amount}元")
            print(f"💰 当前余额: {bonus_amount}元")
            
            success, message = self.account_manager.set_valid_days(phone)
            if not success:
                del self.account_manager.accounts[phone]
                return success, message
            
            success, message = self.account_manager.set_password_and_security(phone)
            if not success:
                del self.account_manager.accounts[phone]
                return success, message
            
            if self.github_enabled:
                self.sync_to_github()
            
            return True, f"✅ 账户创建成功！获得登记奖励{bonus_amount}元"
    
    def find_account(self, identifier):
        if SecurityManager.validate_phone(identifier):
            if identifier in self.account_manager.accounts:
                return identifier, self.account_manager.accounts[identifier], "成功"
            else:
                return None, None, "❌ 手机号未登记"
        else:
            if len(identifier) != 4 or not identifier.isdigit():
                return None, None, "❌ 尾号必须是4位数字"
            
            for phone, info in self.account_manager.accounts.items():
                if info.get("last_four") == identifier:
                    return phone, info, "成功"
            
            return None, None, "❌ 未找到匹配的尾号"
    
    def recharge(self):
        print("\n" + "="*30)
        print("💰 充值")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            identifier = input("请输入手机号或尾号4位: ").strip()
            
            if NavigationManager.handle_back_choice(identifier):
                return False, "已取消充值"
            
            phone, info, message = self.find_account(identifier)
            if phone is None:
                print(message)
                continue
            
            auth_success, auth_message = self.account_manager.authenticate_with_password(phone, info)
            if not auth_success:
                return False, auth_message
            
            while True:
                NavigationManager.show_back_option()
                amount = input("请输入充值金额: ").strip()
                
                if NavigationManager.handle_back_choice(amount):
                    return False, "已取消充值"
                
                try:
                    amount_float = float(amount)
                    if amount_float <= 0:
                        print("❌ 充值金额必须大于0")
                        continue
                except ValueError:
                    print("❌ 充值金额必须是数字")
                    continue
                
                old_balance = info["balance"]
                info["balance"] += amount_float
                info["last_modified"] = TimeManager.get_current_time()
                
                if self.account_manager.save_data():
                    print(f"💰 充值成功: {old_balance}元 → {info['balance']}元")
                    if self.github_enabled:
                        self.sync_to_github()
                    return True, f"✅ 充值成功，手机号{phone}当前余额：{info['balance']:.2f}元"
                else:
                    info["balance"] = old_balance
                    return False, "❌ 充值失败，数据保存错误"
    
    def deduct(self):
        print("\n" + "="*30)
        print("💸 扣款")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            identifier = input("请输入手机号或尾号4位: ").strip()
            
            if NavigationManager.handle_back_choice(identifier):
                return False, "已取消扣款"
            
            phone, info, message = self.find_account(identifier)
            if phone is None:
                print(message)
                continue
            
            auth_success, auth_message = self.account_manager.authenticate_with_password(phone, info)
            if not auth_success:
                return False, auth_message
            
            while True:
                NavigationManager.show_back_option()
                amount = input("请输入扣款金额: ").strip()
                
                if NavigationManager.handle_back_choice(amount):
                    return False, "已取消扣款"
                
                try:
                    amount_float = float(amount)
                    if amount_float <= 0:
                        print("❌ 扣款金额必须大于0")
                        continue
                except ValueError:
                    print("❌ 扣款金额必须是数字")
                    continue
                
                if info["balance"] < amount_float:
                    print(f"❌ 余额不足，当前余额：{info['balance']:.2f}元")
                    continue
                
                old_balance = info["balance"]
                info["balance"] -= amount_float
                info["last_modified"] = TimeManager.get_current_time()
                
                if self.account_manager.save_data():
                    print(f"💸 扣款成功: {old_balance}元 → {info['balance']}元")
                    if self.github_enabled:
                        self.sync_to_github()
                    return True, f"✅ 扣款成功，手机号{phone}当前余额：{info['balance']:.2f}元"
                else:
                    info["balance"] = old_balance
                    return False, "❌ 扣款失败，数据保存错误"
    
    def reset_password(self):
        print("\n" + "="*30)
        print("🔄 重置密码")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            identifier = input("请输入手机号或尾号4位: ").strip()
            
            if NavigationManager.handle_back_choice(identifier):
                return False, "已取消重置密码"
            
            phone, info, message = self.find_account(identifier)
            if phone is None:
                print(message)
                continue
            
            success, message = self.account_manager.reset_password(phone, info)
            if success and self.github_enabled:
                self.sync_to_github()
            return success, message
    
    def get_balance(self):
        print("\n" + "="*30)
        print("📊 查询余额")
        print("="*30)
        
        while True:
            NavigationManager.show_back_option()
            identifier = input("请输入手机号或尾号4位: ").strip()
            
            if NavigationManager.handle_back_choice(identifier):
                return False, "已取消查询"
            
            phone, info, message = self.find_account(identifier)
            if phone is None:
                print(message)
                continue
            
            status_info = ""
            if "expiry_time" in info:
                remaining_time = TimeManager.format_remaining_time(info["expiry_time"])
                status_info = f" | 状态: {info.get('status', '正常')} | 剩余: {remaining_time}"
            
            return True, f"📊 手机号{phone}当前余额：{info['balance']:.2f}元{status_info}"
    
    def list_all_accounts(self):
        if not self.account_manager.accounts:
            return "📭 暂无登记账户"
        
        result = "\n" + "="*80 + "\n"
        result += "📋 所有登记账户\n"
        result += "="*80 + "\n"
        
        for phone, info in self.account_manager.accounts.items():
            has_password = "✅" if info.get("password") else "❌"
            has_security = "✅" if info.get("security_question") else "❌"
            
            status = info.get("status", "正常")
            if "expiry_time" in info and status != "已过期":
                remaining_time = TimeManager.format_remaining_time(info["expiry_time"])
                status_info = f"{status}({remaining_time})"
            else:
                status_info = status
            
            # 显示奖励金额
            bonus_info = f"奖励:{info.get('registration_bonus', 0)}元"
            
            result += f"📱 {phone} | 尾号: {info['last_four']} | 余额: {info['balance']:.2f}元 | "
            result += f"状态: {status_info} | {bonus_info} | 密码: {has_password} | 密保: {has_security}\n"
        
        return result
    
    def check_expired_accounts(self):
        expired_count = 0
        expiring_count = 0
        
        result = "\n" + "="*50 + "\n"
        result += "⏰ 账户有效期检查\n"
        result += "="*50 + "\n"
        
        for phone, info in self.account_manager.accounts.items():
            if "expiry_time" in info:
                if TimeManager.is_expired(info["expiry_time"]):
                    expired_count += 1
                    result += f"❌ {phone} - 已过期\n"
                else:
                    remaining_days = TimeManager.get_remaining_days(info["expiry_time"])
                    if remaining_days <= 3:
                        expiring_count += 1
                        remaining_time = TimeManager.format_remaining_time(info["expiry_time"])
                        result += f"⚠️ {phone} - 即将过期 (剩余{remaining_time})\n"
        
        if expired_count == 0 and expiring_count == 0:
            result += "✅ 所有账户都在有效期内\n"
        else:
            result += f"\n📊 统计: {expired_count}个已过期, {expiring_count}个即将过期\n"
        
        return result
    
    def github_status(self):
        if not self.github_enabled:
            return "GitHub同步未启用"
        
        status = self.git_manager.get_git_status()
        result = "\n" + "="*50 + "\n"
        result += "🔗 GitHub状态\n"
        result += "="*50 + "\n"
        
        if "error" in status:
            result += f"❌ 获取状态失败: {status['error']}\n"
        else:
            result += f"远程仓库: {'✅ 已设置' if status['has_remote'] else '❌ 未设置'}\n"
            if status['has_remote']:
                result += f"仓库地址: {status['remote_url']}\n"
            result += f"未提交更改: {'✅ 有' if status['has_changes'] else '❌ 无'}\n"
        
        return result

def main():
    print("📱 手机号账户管理系统 - 自定义奖励版")
    print("="*50)
    
    use_github = input("是否启用GitHub同步? (y/n): ").strip().lower() == 'y'
    github_repo = None
    
    if use_github:
        github_repo = input("请输入GitHub仓库URL: ").strip()
        if not github_repo:
            print("⚠️ 未提供GitHub仓库URL，禁用同步功能")
            use_github = False
    
    system = PhoneAccountSystem(github_repo=github_repo if use_github else None)
    
    while True:
        print("\n" + "="*50)
        print("📱 手机号账户管理系统")
        print("="*50)
        print("1. 登记手机号 (自定义奖励)")
        print("2. 充值（需要密码）")
        print("3. 扣款（需要密码）")
        print("4. 查询余额")
        print("5. 重置密码（需要密保）")
        print("6. 列出所有账户")
        print("7. 检查过期账户")
        if use_github:
            print("8. GitHub同步状态")
            print("9. 手动同步到GitHub")
            print("10. 从GitHub同步")
            print("11. 退出系统")
        else:
            print("8. 退出系统")
        print("="*50)
        
        choice = input("请选择操作: ").strip()
        
        if choice == '1':
            success, message = system.register_phone()
            print(message)
        elif choice == '2':
            success, message = system.recharge()
            print(message)
        elif choice == '3':
            success, message = system.deduct()
            print(message)
        elif choice == '4':
            success, message = system.get_balance()
            print(message)
        elif choice == '5':
            success, message = system.reset_password()
            print(message)
        elif choice == '6':
            print(system.list_all_accounts())
        elif choice == '7':
            print(system.check_expired_accounts())
        elif use_github and choice == '8':
            print(system.github_status())
        elif use_github and choice == '9':
            success, message = system.sync_to_github()
            print(message)
        elif use_github and choice == '10':
            success, message = system.sync_from_github()
            print(message)
        elif (use_github and choice == '11') or (not use_github and choice == '8'):
            print("感谢使用，再见！👋")
            break
        else:
            print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    main()