// Sample TypeScript frontend API integration for repository inspection
import axios from "axios";

const API_URL = import.meta.env.VITE_API_BASE_URL || "https://api.orders.example.com/v2";

export async function createOrder(customerId: string, amount: number) {
  const response = await axios.post(`${API_URL}/orders`, {
    customerId,
    amount,
  });
  return response.data;
}
