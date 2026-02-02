"""测试 Flask 应用的所有路由"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app import app, get_reports

def test_routes():
    """测试所有路由"""
    with app.test_client() as client:
        print("🧪 开始测试应用...")
        print()

        # 测试首页
        print("1️⃣ 测试首页 /")
        response = client.get('/')
        assert response.status_code == 200
        assert '云端记忆与知识库性能测试'.encode('utf-8') in response.data
        print("   ✅ 首页正常")

        # 测试知识库报告列表
        print("2️⃣ 测试知识库报告列表 /kb")
        response = client.get('/kb')
        assert response.status_code == 200
        assert '知识库测试报告'.encode('utf-8') in response.data
        print("   ✅ 知识库报告列表正常")

        # 测试记忆系统报告列表
        print("3️⃣ 测试记忆系统报告列表 /memory")
        response = client.get('/memory')
        assert response.status_code == 200
        assert '记忆系统测试报告'.encode('utf-8') in response.data
        print("   ✅ 记忆系统报告列表正常")

        # 测试健康检查
        print("4️⃣ 测试健康检查 /health")
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        print("   ✅ 健康检查正常")

        # 测试报告文件访问
        kb_reports, memory_reports = get_reports()

        if kb_reports:
            print(f"5️⃣ 测试访问知识库报告 /report/{kb_reports[0]['filename']}")
            response = client.get(f"/report/{kb_reports[0]['filename']}")
            assert response.status_code == 200
            print("   ✅ 知识库报告访问正常")
        else:
            print("5️⃣ ⚠️  没有找到知识库报告文件")

        if memory_reports:
            print(f"6️⃣ 测试访问记忆系统报告 /report/{memory_reports[0]['filename']}")
            response = client.get(f"/report/{memory_reports[0]['filename']}")
            assert response.status_code == 200
            print("   ✅ 记忆系统报告访问正常")
        else:
            print("6️⃣ ⚠️  没有找到记忆系统报告文件")

        # 测试不存在的报告
        print("7️⃣ 测试访问不存在的报告")
        response = client.get('/report/nonexistent.html')
        assert response.status_code == 404
        print("   ✅ 404 错误处理正常")

        # 测试安全检查（非 .html 文件）
        print("8️⃣ 测试安全检查")
        response = client.get('/report/malicious.txt')
        assert response.status_code == 404
        print("   ✅ 安全检查正常")

        print()
        print("=" * 50)
        print("✅ 所有测试通过！应用运行正常！")
        print("=" * 50)
        print()
        print(f"📊 统计信息:")
        print(f"   - 知识库报告: {len(kb_reports)} 份")
        print(f"   - 记忆系统报告: {len(memory_reports)} 份")
        print()

if __name__ == '__main__':
    try:
        test_routes()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
