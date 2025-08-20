# Smart Tools Cheat Sheet - Quick Reference Guide

## 🎯 **understand** - Learn & Comprehend
**When to use:**
- Learning a new codebase or unfamiliar system
- Understanding architecture and design patterns
- Figuring out how specific features work
- Exploring dependencies and relationships
- Answering "How does X work?" questions

**Example:** `understand(files=["src/auth/"], question="How does the login flow work?")`

## 🔍 **investigate** - Debug & Troubleshoot
**When to use:**
- Debugging errors or bugs
- Finding root causes of problems
- Tracking down performance issues
- Analyzing slow queries or API responses
- Investigating system failures or crashes
- Tracing data flow issues

**Example:** `investigate(files=["src/api/"], problem="API responses taking 10+ seconds")`

## ✅ **validate** - Check & Verify
**When to use:**
- Security audits and vulnerability scanning
- Code quality checks
- Consistency validation across codebase
- Standards compliance verification
- Configuration validation
- Interface consistency checks
- Pre-commit quality gates

**Example:** `validate(files=["src/"], validation_type="security")`

## 💬 **collaborate** - Review & Discuss
**When to use:**
- Code reviews
- Getting expert feedback on implementations
- Technical discussions about approaches
- Reviewing architectural decisions
- Getting suggestions for improvements
- Brainstorming solutions

**Example:** `collaborate(content="my implementation", discussion_type="review")`

## 🚀 **full_analysis** - Comprehensive Analysis
**When to use:**
- Complete codebase assessment
- Major refactoring planning
- Pre-release comprehensive review
- Multi-aspect analysis (security + performance + quality)
- When you need multiple perspectives
- Complex scenarios requiring multiple tool coordination

**Example:** `full_analysis(files=["src/"], focus="all", autonomous=false)`

## 🧪 **propose_tests** - Test Strategy & Generation
**When to use:**
- Identifying test coverage gaps
- Generating test cases for new features
- Planning test strategies
- Prioritizing what to test
- Addressing low test coverage warnings
- TDD planning for new implementations

**Example:** `propose_tests(files=["src/"], test_type="unit", coverage_threshold=0.8)`

## 🚢 **deploy** - Deployment Readiness
**When to use:**
- Pre-deployment validation
- Configuration verification before release
- API contract validation
- Database migration checks
- Environment-specific validation
- Final production readiness assessment

**Example:** `deploy(files=["config/", "src/"], deployment_stage="production")`

---

## 📋 Quick Decision Matrix

| Situation | Use This Tool |
|-----------|--------------|
| "I don't understand this code" | `understand` |
| "Something is broken" | `investigate` |
| "Is this secure?" | `validate` |
| "Review my code" | `collaborate` |
| "Full health check" | `full_analysis` |
| "Need test coverage" | `propose_tests` |
| "Ready to deploy?" | `deploy` |

## 🎯 Common Scenarios

**Starting a new feature:**
1. `understand` - Learn existing patterns
2. `propose_tests` - Plan test strategy
3. `collaborate` - Review implementation plan

**Fixing a bug:**
1. `investigate` - Find root cause
2. `validate` - Check for related issues
3. `propose_tests` - Add regression tests

**Before deployment:**
1. `validate` - Security & quality check
2. `full_analysis` - Comprehensive review
3. `deploy` - Final deployment validation

**Code review:**
1. `collaborate` - Get expert feedback
2. `validate` - Check standards compliance
3. `propose_tests` - Ensure test coverage