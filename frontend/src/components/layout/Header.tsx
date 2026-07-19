import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
export function Header(){const navigate=useNavigate();const logout=useAuthStore(s=>s.logout);return <header className="flex items-center justify-between border-b p-4"><span>ProductOS AI</span><button onClick={()=>{logout();navigate('/login')}}>Sign out</button></header>}
